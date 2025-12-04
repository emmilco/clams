/**
 * Sample C++ code for testing code parsing.
 */

#include <string>

namespace math {

/**
 * Calculate power
 */
int power(int base, int exp) {
    int result = 1;
    for (int i = 0; i < exp; i++) {
        result *= base;
    }
    return result;
}

}

/**
 * Vector class
 */
class Vector {
private:
    double x, y;

public:
    /**
     * Constructor
     */
    Vector(double x, double y) : x(x), y(y) {}

    /**
     * Get magnitude
     */
    double magnitude() {
        return sqrt(x*x + y*y);
    }
};
