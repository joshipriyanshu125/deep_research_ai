const mongoose = require("mongoose");
const Research = require("../models/Research");
const researchEngine = require("../services/researchEngine");

class ResearchWorker {
    constructor() {
        this.activeJobs = new Map(); // researchId -> AbortController
    }

    /**
     * Process a research job
     * @param {string} researchId
     */
    async processJob(researchId) {
        const idStr = researchId.toString();

        if (this.activeJobs.has(idStr)) {
            return;
        }

        const abortController = new AbortController();
        this.activeJobs.set(idStr, abortController);

        try {
            await researchEngine.execute(idStr, abortController.signal);
        } catch (error) {
            console.error(`[ResearchWorker] Uncaught error in job ${idStr}:`, error);
        } finally {
            this.activeJobs.delete(idStr);
        }
    }

    /**
     * Cancel an ongoing research job
     * @param {string} researchId
     */
    async cancelJob(researchId) {
        const idStr = researchId.toString();

        // Abort running engine process
        if (this.activeJobs.has(idStr)) {
            const controller = this.activeJobs.get(idStr);
            if (controller) {
                controller.abort();
            }
            this.activeJobs.delete(idStr);
        }

        if (mongoose.connection.readyState !== 1) return null;

        // Update status in MongoDB
        const updated = await Research.findByIdAndUpdate(
            idStr,
            {
                $set: {
                    status: "cancelled",
                    currentStep: "Research cancelled by user"
                },
                $push: {
                    logs: {
                        timestamp: new Date(),
                        stage: "cancelled",
                        message: "Research job was cancelled by user."
                    }
                }
            },
            { returnDocument: "after" }
        );

        return updated;
    }

    /**
     * Check if a job is currently executing
     * @param {string} researchId
     */
    isJobActive(researchId) {
        return this.activeJobs.has(researchId.toString());
    }
}

// Singleton worker instance
const researchWorker = new ResearchWorker();

module.exports = researchWorker;
