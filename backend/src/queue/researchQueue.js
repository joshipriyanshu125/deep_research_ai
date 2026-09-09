const mongoose = require("mongoose");
const Research = require("../models/Research");
const researchWorker = require("../workers/researchWorker");

class ResearchQueue {
    constructor() {
        this.queue = [];
        this.isProcessing = false;
        this.concurrency = parseInt(process.env.RESEARCH_CONCURRENCY || "2", 10);
        this.activeCount = 0;
    }

    /**
     * Add a research job to the queue
     * @param {string} researchId
     */
    async addJob(researchId) {
        const idStr = researchId.toString();

        if (researchWorker.isJobActive(idStr)) {
            return;
        }

        if (!this.queue.includes(idStr)) {
            this.queue.push(idStr);
        }

        // Process asynchronously without blocking HTTP response
        setImmediate(() => {
            this.processQueue();
        });
    }

    /**
     * Process queued jobs up to concurrency limit
     */
    async processQueue() {
        if (mongoose.connection.readyState !== 1) return;

        while (this.activeCount < this.concurrency && this.queue.length > 0) {
            const researchId = this.queue.shift();
            if (!researchId) continue;

            this.activeCount++;

            // Dispatch worker asynchronously
            researchWorker
                .processJob(researchId)
                .catch((err) => {
                    console.error(`[ResearchQueue] Error processing ${researchId}:`, err.message);
                })
                .finally(() => {
                    this.activeCount = Math.max(0, this.activeCount - 1);
                    // Process next waiting job
                    setImmediate(() => this.processQueue());
                });
        }
    }

    /**
     * Cancel a job in the queue or actively running
     * @param {string} researchId
     */
    async cancelJob(researchId) {
        const idStr = researchId.toString();

        // Remove from pending queue if present
        const idx = this.queue.indexOf(idStr);
        if (idx > -1) {
            this.queue.splice(idx, 1);
        }

        // Signal worker cancellation
        return await researchWorker.cancelJob(idStr);
    }

    /**
     * Resume a cancelled or failed job
     * @param {string} researchId
     */
    async resumeJob(researchId) {
        const idStr = researchId.toString();

        if (mongoose.connection.readyState !== 1) return null;

        const research = await Research.findById(idStr);
        if (!research) {
            throw new Error("Research not found");
        }

        if (research.status === "completed") {
            return research;
        }

        // Reset status to queued
        research.status = "queued";
        research.error = null;
        research.currentStep = "Re-queued in research queue";
        research.logs.push({
            timestamp: new Date(),
            stage: "queued",
            message: "Research job resumed and added back to queue."
        });
        await research.save();

        // Enqueue
        await this.addJob(idStr);

        return research;
    }
}

// Singleton Queue
const researchQueue = new ResearchQueue();

module.exports = researchQueue;
