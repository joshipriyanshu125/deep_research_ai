const assert = require("node:assert/strict");
const test = require("node:test");

// Keep the service tests offline by replacing the SDK before the service is loaded.
// The real API key is never read or emitted by these tests.
let generateContentHandler = async () => ({ text: "test answer" });
class FakeGoogleGenAI {
    constructor() {
        this.models = {
            generateContent: (request) => generateContentHandler(request)
        };
    }
}

const genaiModulePath = require.resolve("@google/genai");
const previousGenaiModule = require.cache[genaiModulePath];
require.cache[genaiModulePath] = {
    id: genaiModulePath,
    filename: genaiModulePath,
    loaded: true,
    exports: { GoogleGenAI: FakeGoogleGenAI }
};

const geminiService = require("../src/services/geminiService");

if (previousGenaiModule) {
    require.cache[genaiModulePath] = previousGenaiModule;
} else {
    delete require.cache[genaiModulePath];
}

const originalApiKey = process.env.GEMINI_API_KEY;
const originalModel = process.env.GEMINI_MODEL;

test.after(() => {
    if (originalApiKey === undefined) delete process.env.GEMINI_API_KEY;
    else process.env.GEMINI_API_KEY = originalApiKey;

    if (originalModel === undefined) delete process.env.GEMINI_MODEL;
    else process.env.GEMINI_MODEL = originalModel;
});

function configureModel(model) {
    process.env.GEMINI_API_KEY = "test-gemini-key";
    process.env.GEMINI_MODEL = model;
}

test("keeps a configured supported model as the first choice", async () => {
    const configuredModel = "gemini-2.5-flash";
    const calls = [];
    configureModel(configuredModel);
    generateContentHandler = async ({ model }) => {
        calls.push(model);
        return { text: "  supported model answer  " };
    };

    const result = await geminiService.askGemini("What is a supported model?");

    assert.deepEqual(calls, [configuredModel]);
    assert.deepEqual(result, {
        answer: "supported model answer",
        model: configuredModel
    });
});

test("falls back when the configured model is unavailable", async () => {
    const configuredModel = "gemini-1.5-flash";
    const calls = [];
    configureModel(configuredModel);
    generateContentHandler = async ({ model }) => {
        calls.push(model);
        if (model === configuredModel) {
            const error = new Error("Model gemini-1.5-flash was not found; key=test-gemini-key");
            error.status = 404;
            throw error;
        }
        return { text: "  fallback answer  " };
    };

    const result = await geminiService.askGemini("What happens after a model is retired?");

    assert.equal(calls[0], configuredModel);
    assert.equal(result.answer, "fallback answer");
    assert.equal(result.model, calls[1]);
    assert.ok(geminiService.FALLBACK_MODELS.includes(result.model));
});

test("returns a safe model-unavailable error after all model candidates fail", async () => {
    const configuredModel = "gemini-1.5-flash";
    const calls = [];
    configureModel(configuredModel);
    generateContentHandler = async ({ model }) => {
        calls.push(model);
        const error = new Error(`Model ${model} was not found; key=test-gemini-key`);
        error.response = { status: 404 };
        throw error;
    };

    await assert.rejects(
        () => geminiService.askGemini("Will all unavailable models fail safely?"),
        (error) => {
            assert.equal(error.status, 502);
            assert.equal(error.code, "GEMINI_MODEL_UNAVAILABLE");
            assert.doesNotMatch(error.message, /test-gemini-key/);
            return true;
        }
    );

    assert.deepEqual(calls, geminiService.getGeminiModelCandidates(configuredModel));
});

test("passes quick-answer cancellation through to the Gemini SDK signal", async () => {
    configureModel("gemini-2.5-flash");
    let sdkSignal;
    generateContentHandler = async ({ config }) => new Promise((_resolve, reject) => {
        sdkSignal = config.abortSignal;
        sdkSignal.addEventListener("abort", () => {
            const error = new Error("SDK request aborted");
            error.name = "AbortError";
            reject(error);
        }, { once: true });
    });

    const controller = new AbortController();
    const request = geminiService.askGemini("cancel this direct answer", { signal: controller.signal });
    await new Promise((resolve) => setImmediate(resolve));
    assert.ok(sdkSignal, "the SDK request should receive an abort signal");

    controller.abort();

    await assert.rejects(request, (error) => error.name === "AbortError" || error.code === "ABORT_ERR");
    assert.equal(sdkSignal.aborted, true);
});
