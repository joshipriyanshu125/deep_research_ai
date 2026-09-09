const mongoose = require("mongoose");

// State Machine States Definition
const RESEARCH_STATES = {
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

const researchSchema = new mongoose.Schema(
    {
        user: {
            type: mongoose.Schema.Types.ObjectId,
            ref: "User",
            required: [true, "Research must belong to a user"],
            index: true
        },
        query: {
            type: String,
            required: [true, "Research query is required"],
            trim: true
        },
        title: {
            type: String,
            trim: true,
            default: function () {
                if (this.query) {
                    return this.query.length > 80
                        ? this.query.substring(0, 77) + "..."
                        : this.query;
                }
                return "Untitled Research";
            }
        },
        topic: {
            type: String,
            trim: true,
            default: ""
        },
        status: {
            type: String,
            enum: [
                "queued",
                "planning",
                "searching",
                "collecting",
                "analyzing",
                "verifying",
                "synthesizing",
                "report_generation",
                "quality_check",
                "completed",
                "failed",
                "retry",
                "cancelled",
                // Backwards compatibility aliases
                "researching",
                "fact_checking",
                "writing",
                "in_progress",
                "pending",
                "paused"
            ],
            default: "queued",
            index: true
        },
        progress: {
            type: Number,
            min: 0,
            max: 100,
            default: 0
        },
        currentStep: {
            type: String,
            default: "Queued for processing"
        },
        failedStage: {
            type: String,
            default: null
        },
        retryCount: {
            type: Number,
            default: 0
        },
        maxRetries: {
            type: Number,
            default: 3
        },
        depth: {
            type: String,
            enum: ["quick", "standard", "deep"],
            default: "standard"
        },
        findings: {
            type: [mongoose.Schema.Types.Mixed],
            default: []
        },
        sources: {
            type: [
                {
                    title: String,
                    url: String,
                    snippet: String,
                    relevanceScore: Number,
                    collectedAt: { type: Date, default: Date.now }
                }
            ],
            default: []
        },
        qualityScore: {
            type: Number,
            default: null
        },
        qualityCheckResults: {
            type: mongoose.Schema.Types.Mixed,
            default: {}
        },
        logs: {
            type: [
                {
                    timestamp: { type: Date, default: Date.now },
                    message: String,
                    stage: String,
                    state: String
                }
            ],
            default: []
        },
        error: {
            type: String,
            default: null
        },
        startedAt: {
            type: Date,
            default: null
        },
        completedAt: {
            type: Date,
            default: null
        },
        isPublic: {
            type: Boolean,
            default: false
        }
    },
    {
        timestamps: true,
        toJSON: {
            virtuals: true,
            transform: function (doc, ret) {
                ret.research_id = ret._id.toString();
                ret.id = ret._id.toString();
                delete ret.__v;
                return ret;
            }
        }
    }
);

// Virtual for research_id
researchSchema.virtual("research_id").get(function () {
    return this._id.toString();
});

const Research = mongoose.model("Research", researchSchema);

Research.STATES = RESEARCH_STATES;

module.exports = Research;
