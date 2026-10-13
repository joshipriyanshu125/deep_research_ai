const mongoose = require("mongoose");
const Research = require("../models/Research");
const researchWorker = require("../workers/researchWorker");
const stateMachine = require("../services/researchStateMachine");

// Every state a running worker can own. The queue itself lives in memory, so a
// process restart or a nodemon reload orphans these documents: they stay at
// their in-flight status forever unless they are re-queued on startup.
const INTERRUPTED_STATES = [
    "queued",
    "retry",
    "pending",
    "planning",
    "searching",
    "collecting",
    "analyzing",
    "verifying",
    "synthesizing",
    "report_generation",
    "quality_check",
    // Legacy aliases still accepted by the Research schema
    "researching",
    "fact_checking",
    "writing",
    "in_progress",
    "paused"
];

class ResearchQueue {
    constructor() {
        this.queue = [];
        this.isProcessing = false;
        this.concurrency = parseInt(process.env.RESEARCH_CONCURRENCY || "2", 10);
        this.activeCount = 0;
        this.connectionWaiter = null;
    }

    /**
     * Kick the queue now, or as soon as MongoDB becomes reachable.
     *
     * Previously processQueue() returned silently while the connection was
     * down, which left an already-dequeued job stranded in memory until some
     * later request happened to trigger another run.
     */
    scheduleProcessing() {
        if (mongoose.connection.readyState === 1) {
            setImmediate(() => this.processQueue());
            return;
        }

        if (this.connectionWaiter) return;
        this.connectionWaiter = () => {
            this.connectionWaiter = null;
            setImmediate(() => this.processQueue());
        };
        mongoose.connection.once("connected", this.connectionWaiter);
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
        this.scheduleProcessing();
    }

    /**
     * Re-queue documents that were left behind by a previous process.
     *
     * In-flight statuses are reset to 'queued' with a compare-and-set so a job
     * that finished (or was cancelled) while we were reading it is never
     * resurrected. Already active or already queued jobs are skipped.
     * @returns {Promise<number>} number of re-queued jobs
     */
    async recoverInterruptedJobs() {
        if (mongoose.connection.readyState !== 1) return 0;

        const interrupted = await Research.find({ status: { $in: INTERRUPTED_STATES } })
            .select("_id status");

        let recovered = 0;
        for (const doc of interrupted) {
            const idStr = doc._id.toString();
            if (researchWorker.isJobActive(idStr) || this.queue.includes(idStr)) continue;

            if (doc.status !== "queued" && doc.status !== "retry") {
                const requeued = await Research.findOneAndUpdate(
                    { _id: idStr, status: doc.status },
                    {
                        $set: {
                            status: "queued",
                            progress: 0,
                            currentStep: "Recovered after a server restart and re-queued for processing"
                        },
                        $push: {
                            logs: {
                                timestamp: new Date(),
                                state: "queued",
                                stage: "recovery",
                                message: `Interrupted in '${doc.status}' state; re-queued after restart.`
                            }
                        }
                    },
                    { returnDocument: "after" }
                );
                // The status changed under us (completed/cancelled/failed) —
                // the terminal state wins.
                if (!requeued) continue;
            }

            await this.addJob(idStr);
            recovered += 1;
        }

        if (recovered > 0) {
            console.log(`[ResearchQueue] Recovered ${recovered} interrupted research job(s).`);
        }
        return recovered;
    }

    /**
     * Process queued jobs up to concurrency limit
     */
    async processQueue() {
        if (mongoose.connection.readyState !== 1) {
            // Keep the pending jobs instead of dropping them: resume as soon
            // as the database comes back.
            this.scheduleProcessing();
            return;
        }

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
     * Resume a cancelled, paused, or failed job
     * @param {string} researchId
     */
    async resumeJob(researchId) {
        const idStr = researchId.toString();

        if (mongoose.connection.readyState !== 1) return null;

        let research = await Research.findById(idStr);
        if (!research) {
            throw new Error("Research not found");
        }

        if (research.status === "completed") {
            return research;
        }

        // If cancellation and resume arrive together, let the existing
        // worker finish its abort boundary before deciding whether to enqueue
        // a fresh attempt. This keeps one active worker per research id.
        if (researchWorker.isJobActive(idStr)) {
            await researchWorker.waitForJob(idStr);
            research = await Research.findById(idStr);
            if (!research || research.status === "completed") return research;
        }

        // Use state machine to transition to QUEUED
        if (research.status !== stateMachine.STATES.QUEUED) {
            const queued = await stateMachine.transition(idStr, stateMachine.STATES.QUEUED, {
                message: "Research job resumed and added back to queue."
            });
            if (!queued) return await Research.findById(idStr);
            research = queued;
        }

        // Enqueue
        await this.addJob(idStr);

        return research;
    }

    /**
     * Retry a failed research job
     * @param {string} researchId
     */
    async retryJob(researchId) {
        const idStr = researchId.toString();

        if (mongoose.connection.readyState !== 1) return null;

        const research = await stateMachine.retry(idStr);

        // Add back to processing queue
        await this.addJob(idStr);

        return research;
    }
}

// Singleton Queue
const researchQueue = new ResearchQueue();

module.exports = researchQueue;
