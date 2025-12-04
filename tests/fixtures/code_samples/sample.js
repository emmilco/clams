/**
 * Sample JavaScript module for testing code parsing.
 */

/**
 * Simple function
 */
function greet(name) {
    return `Hello, ${name}!`;
}

/**
 * Arrow function
 */
const multiply = (a, b) => a * b;

/**
 * Class with methods
 */
class Counter {
    constructor() {
        this.count = 0;
    }

    /**
     * Increment counter
     */
    increment() {
        this.count++;
        return this.count;
    }
}

module.exports = { greet, multiply, Counter };
