/**
 * Sample C code for testing code parsing.
 */

#include <stdio.h>

/**
 * Add two integers
 */
int add(int a, int b) {
    return a + b;
}

/**
 * Calculate factorial
 */
int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

struct Point {
    int x;
    int y;
};
