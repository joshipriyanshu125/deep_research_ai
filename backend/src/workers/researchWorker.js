const mongoose = require("mongoose");
const Research = require("../models/Research");
const researchEngine = require("../services/researchEngine");

class ResearchWorker {
    constructor() {
        this.activeJobs = new Map(); // researchId -> AbortController
        this.jobPromises = new Map(); // researchId -> promise that settles after engine cleanup
        this.cancelPromises = new Map(); // researchId -> promise that persists cancelled state
    }

    /**
     * Process a research job
     * @param {string} researchId
     */
    async processJob(researchId) {
        const idStr = researchId.toString();

        if (this.activeJobs.has(idStr)) {
            return this.jobPromises.get(idStr);
        }

        const abortController = new AbortController();
        this.activeJobs.set(idStr, abortController);

        const jobPromise = (async () => {
            try {
                await researchEngine.execute(idStr, abortController.signal);
            } catch (error) {
                console.error(`[ResearchWorker] Uncaught error in job ${idStr}:`, error);
            } finally {
                // Keep the active marker until the engine has actually
                // unwound. This prevents an immediate resume from starting a
                // second worker for the same research id.
                if (this.activeJobs.get(idStr) === abortController) {
                    this.activeJobs.delete(idStr);
                }
                if (this.jobPromises.get(idStr) === jobPromise) {
                    this.jobPromises.delete(idStr);
                }
            }
        })();
        this.jobPromises.set(idStr, jobPromise);
        return jobPromise;
    }

    /**
     * Cancel an ongoing research job
     * @param {string} researchId
     */
    async cancelJob(researchId) {
        const idStr = researchId.toString();

        const existingCancellation = this.cancelPromises.get(idStr);
        if (existingCancellation) return existingCancellation;

        const cancellation = this.persistCancellation(idStr);
        this.cancelPromises.set(idStr, cancellation);
        try {
            return await cancellation;
        } finally {
            if (this.cancelPromises.get(idStr) === cancellation) {
                this.cancelPromises.delete(idStr);
            }
        }
    }

    async persistCancellation(idStr) {

        // Abort running engine process, but retain the active marker until the
        // process unwinds. Queue resume uses the same completion promise to
        // avoid a cancel/resume double-dispatch race.
        const controller = this.activeJobs.get(idStr);
        const completion = this.jobPromises.get(idStr);
        if (controller) controller.abort();

        if (mongoose.connection.readyState !== 1) return null;

        // Update status in MongoDB
        const updated = await Research.findOneAndUpdate(
            {
                _id: idStr,
                status: { $nin: ["completed", "cancelled"] }
            },
            {
                $set: {
                    status: "cancelled",
                    currentStep: "Research cancelled by user"
                },
                $push: {
                    logs: {
                        timestamp: new Date(),
                        state: "cancelled",
                        stage: "cancelled",
                        message: "Research job was cancelled by user."
                    }
                }
            },
            { returnDocument: "after" }
        );

        // A completed or already-cancelled job wins over a late Stop request.
        const terminal = updated || await Research.findById(idStr);
        if (completion) await completion;
        return terminal;
    }

    /**
     * Check if a job is currently executing
     * @param {string} researchId
     */
    isJobActive(researchId) {
        return this.activeJobs.has(researchId.toString());
    }

    /**
     * Wait for a running job to finish its cancellation/cleanup boundary.
     * @param {string} researchId
     */
    async waitForJob(researchId) {
        const idStr = researchId.toString();
        const promise = this.jobPromises.get(idStr);
        if (promise) await promise;
        const cancellation = this.cancelPromises.get(idStr);
        if (cancellation) await cancellation;
    }
}

// Singleton worker instance
const researchWorker = new ResearchWorker();

module.exports = researchWorker;
