/// Sample Swift code for testing code parsing

/// Protocol for shapes
protocol Shape {
    func area() -> Double
}

/// Rectangle struct
struct Rectangle: Shape {
    let width: Double
    let height: Double

    /// Calculate area
    func area() -> Double {
        return width * height
    }
}

/// Circle class
class Circle: Shape {
    let radius: Double

    /// Initialize with radius
    init(radius: Double) {
        self.radius = radius
    }

    /// Calculate area
    func area() -> Double {
        return 3.14159 * radius * radius
    }
}
