/**
 * Sample Java class for testing code parsing.
 */
public class Calculator {
    private int value;

    /**
     * Constructor
     */
    public Calculator(int initialValue) {
        this.value = initialValue;
    }

    /**
     * Add to current value
     */
    public int add(int x) {
        this.value += x;
        return this.value;
    }

    /**
     * Get current value
     */
    public int getValue() {
        return this.value;
    }
}

/**
 * Interface for operations
 */
public interface Operation {
    int execute(int x, int y);
}
