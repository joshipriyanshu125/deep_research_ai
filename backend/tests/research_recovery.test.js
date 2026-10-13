const assert = require('node:assert/strict');
const test = require('node:test');

const mongoose = require('mongoose');
const Research = require('../src/models/Research');
const researchQueue = require('../src/queue/researchQueue');
const researchWorker = require('../src/workers/researchWorker');

function setReadyState(value) {
    mongoose.connection.readyState = value;
}

test('interrupted research documents are re-queued on recovery', async () => {
    const previousReadyState = mongoose.connection.readyState;
    const originalFind = Research.find;
    const originalFindOneAndUpdate = Research.findOneAndUpdate;
    const originalAddJob = researchQueue.addJob;

    const docs = [
        { _id: 'stalled-search', status: 'searching' },
        { _id: 'lost-queue', status: 'queued' }
    ];
    let findQuery = null;
    const updates = [];
    const added = [];

    setReadyState(1);
    Research.find = (query) => {
        findQuery = query;
        return { select: async () => docs };
    };
    Research.findOneAndUpdate = async (flt, update) => {
        updates.push({ flt, update });
        return { _id: flt._id, status: 'queued' };
    };
    researchQueue.addJob = async (id) => {
        added.push(String(id));
    };

    try {
        const recovered = await researchQueue.recoverInterruptedJobs();

        assert.equal(recovered, 2);
        assert.deepEqual([...added].sort(), ['lost-queue', 'stalled-search']);

        const statuses = new Set(findQuery.status.$in);
        for (const expected of ['queued', 'retry', 'planning', 'searching', 'quality_check']) {
            assert.ok(statuses.has(expected), `expected '${expected}' in recovery query`);
        }

        // The in-flight run is reset with a compare-and-set; the already
        // queued run is only re-dispatched.
        assert.equal(updates.length, 1);
        assert.equal(updates[0].flt.status, 'searching');
        assert.equal(updates[0].update.$set.status, 'queued');
        assert.equal(updates[0].update.$set.progress, 0);
        assert.equal(updates[0].update.$push.logs.stage, 'recovery');
    } finally {
        Research.find = originalFind;
        Research.findOneAndUpdate = originalFindOneAndUpdate;
        researchQueue.addJob = originalAddJob;
        setReadyState(previousReadyState);
    }
});

test('recovery never resurrects a run that finished concurrently', async () => {
    const previousReadyState = mongoose.connection.readyState;
    const originalFind = Research.find;
    const originalFindOneAndUpdate = Research.findOneAndUpdate;
    const originalAddJob = researchQueue.addJob;

    const added = [];
    setReadyState(1);
    Research.find = () => ({
        select: async () => [{ _id: 'just-finished', status: 'synthesizing' }]
    });
    // The compare-and-set misses: the run reached a terminal state first.
    Research.findOneAndUpdate = async () => null;
    researchQueue.addJob = async (id) => {
        added.push(String(id));
    };

    try {
        const recovered = await researchQueue.recoverInterruptedJobs();
        assert.equal(recovered, 0);
        assert.deepEqual(added, []);
    } finally {
        Research.find = originalFind;
        Research.findOneAndUpdate = originalFindOneAndUpdate;
        researchQueue.addJob = originalAddJob;
        setReadyState(previousReadyState);
    }
});

test('a job queued while MongoDB is down resumes when the connection opens', async () => {
    const previousReadyState = mongoose.connection.readyState;
    const originalProcessQueue = researchQueue.processQueue;

    let processed = 0;
    researchQueue.processQueue = async () => {
        processed += 1;
    };
    researchQueue.queue.length = 0;
    researchQueue.connectionWaiter = null;

    try {
        setReadyState(0);
        await researchQueue.addJob('disconnected-job');
        assert.deepEqual(researchQueue.queue, ['disconnected-job']);

        await new Promise((resolve) => setImmediate(resolve));
        assert.equal(processed, 0, 'must not dispatch without a database');

        setReadyState(1);
        mongoose.connection.emit('connected');
        await new Promise((resolve) => setImmediate(resolve));

        assert.ok(processed >= 1, 'queue must resume once the database is reachable');
        assert.equal(researchQueue.connectionWaiter, null);
    } finally {
        researchQueue.processQueue = originalProcessQueue;
        researchQueue.queue.length = 0;
        if (researchQueue.connectionWaiter) {
            mongoose.connection.removeListener('connected', researchQueue.connectionWaiter);
            researchQueue.connectionWaiter = null;
        }
        setReadyState(previousReadyState);
    }
});

test('the engine waits for the database instead of silently skipping a job', async () => {
    const previousReadyState = mongoose.connection.readyState;
    const researchEngine = require('../src/services/researchEngine');

    try {
        setReadyState(1);
        assert.equal(await researchEngine.awaitDatabaseConnection(50), true);

        setReadyState(0);
        const startedAt = Date.now();
        assert.equal(await researchEngine.awaitDatabaseConnection(50), false);
        assert.ok(Date.now() - startedAt >= 40, 'must give the database a chance to reconnect');
    } finally {
        setReadyState(previousReadyState);
    }
});
