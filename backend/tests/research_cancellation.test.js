const assert = require('node:assert/strict');
const test = require('node:test');

const mongoose = require('mongoose');
const Research = require('../src/models/Research');
const stateMachine = require('../src/services/researchStateMachine');
const researchEngine = require('../src/services/researchEngine');
const researchWorker = require('../src/workers/researchWorker');

test('state transitions do not save a stale document after a concurrent status change', async () => {
    const previousReadyState = mongoose.connection.readyState;
    const originalFindOneAndUpdate = Research.findOneAndUpdate;
    const originalFindById = Research.findById;
    mongoose.connection.readyState = 1;

    let staleSaveCalls = 0;
    const staleDocument = {
        _id: 'stale-research',
        status: stateMachine.STATES.PLANNING,
        progress: 15,
        startedAt: new Date(),
        logs: [],
        save: async () => { staleSaveCalls += 1; }
    };

    Research.findOneAndUpdate = async () => null;
    Research.findById = async () => ({ status: stateMachine.STATES.CANCELLED });
    try {
        const updated = await stateMachine.transition(staleDocument, stateMachine.STATES.SEARCHING, {
            message: 'stale transition must not win'
        });
        assert.equal(updated, null);
        assert.equal(staleSaveCalls, 0);
        const failed = await stateMachine.fail('stale-research', new Error('late stage error'), 'testing');
        assert.equal(failed.status, stateMachine.STATES.CANCELLED);
        assert.equal(stateMachine.canTransition(stateMachine.STATES.COMPLETED, stateMachine.STATES.CANCELLED), false);
    } finally {
        Research.findOneAndUpdate = originalFindOneAndUpdate;
        Research.findById = originalFindById;
        mongoose.connection.readyState = previousReadyState;
    }
});

test('worker keeps the active marker until cancellation cleanup finishes', async () => {
    const previousReadyState = mongoose.connection.readyState;
    const originalExecute = researchEngine.execute;
    const originalFindOneAndUpdate = Research.findOneAndUpdate;
    const originalFindById = Research.findById;
    const id = 'cancel-cleanup-research';
    let started;
    const startedPromise = new Promise((resolve) => { started = resolve; });

    mongoose.connection.readyState = 1;
    researchWorker.activeJobs.clear();
    researchWorker.jobPromises.clear();
    researchWorker.cancelPromises.clear();
    researchEngine.execute = async (_researchId, signal) => {
        started();
        await new Promise((resolve) => setTimeout(resolve, 30));
        assert.equal(signal.aborted, true);
    };
    Research.findOneAndUpdate = async () => ({ _id: id, status: 'cancelled' });
    Research.findById = async () => ({ _id: id, status: 'cancelled' });

    try {
        const running = researchWorker.processJob(id);
        await startedPromise;

        const cancellation = researchWorker.cancelJob(id);
        await new Promise((resolve) => setImmediate(resolve));
        assert.equal(researchWorker.isJobActive(id), true);

        const cancelled = await cancellation;
        await running;
        assert.equal(cancelled.status, 'cancelled');
        assert.equal(researchWorker.isJobActive(id), false);
    } finally {
        researchWorker.activeJobs.clear();
        researchWorker.jobPromises.clear();
        researchWorker.cancelPromises.clear();
        researchEngine.execute = originalExecute;
        Research.findOneAndUpdate = originalFindOneAndUpdate;
        Research.findById = originalFindById;
        mongoose.connection.readyState = previousReadyState;
    }
});
