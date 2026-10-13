const mongoose = require("mongoose");
const Research = require("../models/Research");

const STATES = {
    QUEUED: "queued",
    PLANNING: "planning",
    SEARCHING: "searching",
    COLLECTING: "collecting",
    ANALYZING: "analyzing",
    VERIFYING: "verifying",
    SYNTHESIZING: "synthesizing",
    REPORT_GENERATION: "report_generation",
    QUALITY_CHECK: "quality_check",
    COMPLETED: "completed",
    FAILED: "failed",
    RETRY: "retry",
    CANCELLED: "cancelled"
};

// Transition matrix mapping valid target states for each current state
const TRANSITIONS = {
    [STATES.QUEUED]: [STATES.PLANNING, STATES.CANCELLED, STATES.FAILED],
    [STATES.PLANNING]: [STATES.SEARCHING, STATES.CANCELLED, STATES.FAILED],
    [STATES.SEARCHING]: [STATES.COLLECTING, STATES.CANCELLED, STATES.FAILED],
    [STATES.COLLECTING]: [STATES.ANALYZING, STATES.CANCELLED, STATES.FAILED],
    [STATES.ANALYZING]: [STATES.VERIFYING, STATES.CANCELLED, STATES.FAILED],
    [STATES.VERIFYING]: [STATES.SYNTHESIZING, STATES.CANCELLED, STATES.FAILED],
    [STATES.SYNTHESIZING]: [STATES.REPORT_GENERATION, STATES.CANCELLED, STATES.FAILED],
    [STATES.REPORT_GENERATION]: [STATES.QUALITY_CHECK, STATES.CANCELLED, STATES.FAILED],
    [STATES.QUALITY_CHECK]: [STATES.COMPLETED, STATES.RETRY, STATES.FAILED, STATES.CANCELLED],
    [STATES.COMPLETED]: [STATES.RETRY, STATES.QUEUED],
    [STATES.FAILED]: [STATES.RETRY, STATES.QUEUED, STATES.CANCELLED],
    [STATES.RETRY]: [STATES.QUEUED, STATES.PLANNING, STATES.FAILED, STATES.CANCELLED],
    [STATES.CANCELLED]: [STATES.QUEUED, STATES.RETRY]
};

// Progress percentage mapping per state
const STATE_PROGRESS = {
    [STATES.QUEUED]: 0,
    [STATES.PLANNING]: 15,
    [STATES.SEARCHING]: 30,
    [STATES.COLLECTING]: 45,
    [STATES.ANALYZING]: 60,
    [STATES.VERIFYING]: 75,
    [STATES.SYNTHESIZING]: 85,
    [STATES.REPORT_GENERATION]: 92,
    [STATES.QUALITY_CHECK]: 98,
    [STATES.COMPLETED]: 100,
    [STATES.FAILED]: 0,
    [STATES.RETRY]: 5,
    [STATES.CANCELLED]: 0
};

class ResearchStateMachine {
    constructor() {
        this.STATES = STATES;
        this.TRANSITIONS = TRANSITIONS;
        this.STATE_PROGRESS = STATE_PROGRESS;
    }

    /**
     * Check if a transition is valid
     * @param {string} fromState
     * @param {string} toState
     * @returns {boolean}
     */
    canTransition(fromState, toState) {
        if (!fromState || !toState) return false;
        // Any non-terminal state can transition to CANCELLED. A completed
        // job is immutable with respect to Stop.
        if (toState === STATES.CANCELLED) return fromState !== STATES.COMPLETED;
        // Any state can transition to FAILED
        if (toState === STATES.FAILED) return true;

        const allowed = this.TRANSITIONS[fromState];
        if (!allowed) return true; // Flexible for aliases
        return allowed.includes(toState);
    }

    /**
     * Transition a research document to target state with atomic validation & logging
     * @param {string|Object} researchOrId
     * @param {string} targetState
     * @param {Object} metadata
     */
    async transition(researchOrId, targetState, metadata = {}) {
        if (mongoose.connection.readyState !== 1) return null;

        const isDocument = typeof researchOrId === "object" && researchOrId?._id;
        const id = isDocument ? researchOrId._id : researchOrId;
        const research = isDocument
            ? researchOrId
            : await Research.findById(id);

        if (!research) {
            throw new Error(`Research document ${id} not found for state transition`);
        }

        const currentState = research.status;

        if ([STATES.COMPLETED, STATES.CANCELLED].includes(currentState) &&
            [STATES.CANCELLED, STATES.FAILED].includes(targetState)) {
            return null;
        }

        // Verify transition validity
        if (!this.canTransition(currentState, targetState)) {
            console.warn(
                `[StateMachine] Warning: Transition from '${currentState}' to '${targetState}' is outside standard DAG, applying override.`
            );
        }

        // Prepare updates
        const progress = metadata.progress !== undefined
            ? metadata.progress
            : (this.STATE_PROGRESS[targetState] ?? research.progress);

        const currentStep = metadata.step || metadata.message || `State: ${targetState.toUpperCase()}`;

        const set = {
            status: targetState,
            progress,
            currentStep
        };
        if (targetState === STATES.COMPLETED) {
            set.completedAt = new Date();
        } else if (targetState === STATES.PLANNING && !research.startedAt) {
            set.startedAt = new Date();
        }

        if (metadata.error) {
            set.error = metadata.error;
            set.failedStage = currentState;
        }

        // The status predicate makes a transition a compare-and-set. A worker
        // holding an older document can therefore not save over a concurrent
        // cancellation or completion.
        const updated = await Research.findOneAndUpdate(
            { _id: id, status: currentState },
            {
                $set: set,
                $push: {
                    logs: {
                        timestamp: new Date(),
                        state: targetState,
                        stage: targetState,
                        message: metadata.message || `Transitioned from ${currentState} to ${targetState}`
                    }
                }
            },
            { returnDocument: "after", runValidators: true }
        );

        // A missing update means the state changed after it was read (usually
        // because Stop won the race). Do not resurrect the stale state.
        return updated || null;
    }

    /**
     * Mark a research job as FAILED
     * @param {string} researchId
     * @param {Error|string} error
     * @param {string} stage
     */
    async fail(researchId, error, stage = "unknown") {
        if (mongoose.connection.readyState !== 1) return null;

        const errorMessage = error instanceof Error ? error.message : String(error);

        const updated = await Research.findOneAndUpdate(
            {
                _id: researchId,
                status: { $nin: [STATES.COMPLETED, STATES.CANCELLED] }
            },
            {
                $set: {
                    status: STATES.FAILED,
                    error: errorMessage,
                    failedStage: stage,
                    currentStep: `Failed during ${stage.toUpperCase()} stage: ${errorMessage}`
                },
                $push: {
                    logs: {
                        timestamp: new Date(),
                        state: STATES.FAILED,
                        stage: stage,
                        message: `Execution failed at ${stage}: ${errorMessage}`
                    }
                }
            },
            { returnDocument: "after" }
        );

        // Preserve an already-terminal result if a late stage error arrives.
        return updated || await Research.findById(researchId);
    }

    /**
     * Trigger RETRY on a failed or cancelled research job
     * @param {string} researchId
     */
    async retry(researchId) {
        if (mongoose.connection.readyState !== 1) return null;

        const research = await Research.findById(researchId);
        if (!research) {
            throw new Error("Research not found");
        }

        if (research.retryCount >= research.maxRetries) {
            throw new Error(`Maximum retries (${research.maxRetries}) exceeded for research ${researchId}`);
        }

        const nextRetryCount = research.retryCount + 1;
        const retryUpdate = await Research.findOneAndUpdate(
            { _id: researchId, status: research.status },
            {
                $set: {
                    status: STATES.RETRY,
                    error: null,
                    currentStep: `Retrying research (Attempt ${nextRetryCount}/${research.maxRetries})`
                },
                $inc: { retryCount: 1 },
                $push: {
                    logs: {
                        timestamp: new Date(),
                        state: STATES.RETRY,
                        stage: "retry",
                        message: `Initiating retry attempt ${nextRetryCount} of ${research.maxRetries}. Previous failure at: ${research.failedStage || "unknown"}`
                    }
                }
            },
            { returnDocument: "after" }
        );
        if (!retryUpdate) {
            const latest = await Research.findById(researchId);
            if (!latest) throw new Error("Research not found");
            return latest;
        }

        // Transition back to QUEUED for execution
        const queued = await this.transition(researchId, STATES.QUEUED, {
            message: `Re-queued after retry attempt ${nextRetryCount}`
        });

        return queued || await Research.findById(researchId);
    }
}

// Singleton state machine instance
const researchStateMachine = new ResearchStateMachine();

module.exports = researchStateMachine;
