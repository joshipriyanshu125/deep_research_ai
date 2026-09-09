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
        // Any state can transition to FAILED or CANCELLED
        if (toState === STATES.FAILED || toState === STATES.CANCELLED) return true;

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

        const id = typeof researchOrId === "string" ? researchOrId : researchOrId._id;
        const research = typeof researchOrId === "object" && researchOrId._id
            ? researchOrId
            : await Research.findById(id);

        if (!research) {
            throw new Error(`Research document ${id} not found for state transition`);
        }

        const currentState = research.status;

        // Verify transition validity
        if (!this.canTransition(currentState, targetState)) {
            console.warn(
                `[StateMachine] Warning: Transition from '${currentState}' to '${targetState}' is outside standard DAG, applying override.`
            );
        }

        // Prepare updates
        const progress = metadata.progress !== undefined
            ? metadata.progress
            : (this.STATE_PROGRESS[targetState] || research.progress);

        const currentStep = metadata.step || metadata.message || `State: ${targetState.toUpperCase()}`;

        research.status = targetState;
        research.progress = progress;
        research.currentStep = currentStep;

        if (targetState === STATES.COMPLETED) {
            research.completedAt = new Date();
        } else if (targetState === STATES.PLANNING && !research.startedAt) {
            research.startedAt = new Date();
        }

        if (metadata.error) {
            research.error = metadata.error;
            research.failedStage = currentState;
        }

        // Push state log
        research.logs.push({
            timestamp: new Date(),
            state: targetState,
            stage: targetState,
            message: metadata.message || `Transitioned from ${currentState} to ${targetState}`
        });

        await research.save();
        return research;
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

        return await Research.findByIdAndUpdate(
            researchId,
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

        research.retryCount += 1;
        research.status = STATES.RETRY;
        research.error = null;
        research.currentStep = `Retrying research (Attempt ${research.retryCount}/${research.maxRetries})`;
        research.logs.push({
            timestamp: new Date(),
            state: STATES.RETRY,
            stage: "retry",
            message: `Initiating retry attempt ${research.retryCount} of ${research.maxRetries}. Previous failure at: ${research.failedStage || "unknown"}`
        });
        await research.save();

        // Transition back to QUEUED for execution
        await this.transition(research, STATES.QUEUED, {
            message: `Re-queued after retry attempt ${research.retryCount}`
        });

        return research;
    }
}

// Singleton state machine instance
const researchStateMachine = new ResearchStateMachine();

module.exports = researchStateMachine;
