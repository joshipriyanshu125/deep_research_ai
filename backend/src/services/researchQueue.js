const queue = require("../queue/researchQueue");

module.exports = {
    enqueue: (id) => queue.addJob(id),
    cancel: (id) => queue.cancelJob(id),
    resume: (id) => queue.resumeJob(id),
    retry: (id) => queue.retryJob(id),
    addJob: (id) => queue.addJob(id),
    cancelJob: (id) => queue.cancelJob(id),
    resumeJob: (id) => queue.resumeJob(id),
    retryJob: (id) => queue.retryJob(id)
};
