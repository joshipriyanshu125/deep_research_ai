const mongoose = require("mongoose");

const reportSchema = new mongoose.Schema(
    {
        user: {
            type: mongoose.Schema.Types.ObjectId,
            ref: "User",
            required: [true, "Report must belong to a user"],
            index: true
        },
        research: {
            type: mongoose.Schema.Types.ObjectId,
            ref: "Research",
            required: [true, "Report must belong to a research item"],
            index: true
        },
        title: {
            type: String,
            required: [true, "Report title is required"],
            trim: true
        },
        summary: {
            type: String,
            default: ""
        },
        content: {
            type: String,
            required: [true, "Report content is required"]
        },
        sections: {
            type: [
                {
                    heading: String,
                    body: String
                }
            ],
            default: []
        },
        citations: {
            type: [
                {
                    index: Number,
                    citationId: String,
                    sourceUrl: String,
                    url: String,
                    title: String,
                    sourceType: String,
                    publisherUrl: String,
                    snippet: String,
                    evidenceIds: [String],
                    verificationFor: [String],
                    verificationStatus: String,
                    isVerificationSource: Boolean
                }
            ],
            default: []
        },
        verificationSummary: {
            type: mongoose.Schema.Types.Mixed,
            default: {}
        },
        sources: {
            type: [mongoose.Schema.Types.Mixed],
            default: []
        },
        evidence: {
            type: [mongoose.Schema.Types.Mixed],
            default: []
        },
        factChecks: {
            type: [mongoose.Schema.Types.Mixed],
            default: []
        },
        analysis: {
            type: mongoose.Schema.Types.Mixed,
            default: null
        },
        qualityScore: {
            type: Number,
            default: null
        },
        qualityCheckResults: {
            type: mongoose.Schema.Types.Mixed,
            default: {}
        },
        status: {
            type: String,
            enum: ["draft", "published"],
            default: "published"
        },
        isPublic: {
            type: Boolean,
            default: false
        }
    },
    {
        timestamps: true,
        toJSON: {
            transform: function (doc, ret) {
                delete ret.__v;
                return ret;
            }
        }
    }
);

const Report = mongoose.model("Report", reportSchema);

module.exports = Report;
