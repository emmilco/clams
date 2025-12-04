/// Sample Rust module for testing code parsing

pub struct Point {
    x: i32,
    y: i32,
}

pub enum Color {
    Red,
    Green,
    Blue,
}

/// Calculate distance between two points
pub fn distance(p1: &Point, p2: &Point) -> f64 {
    let dx = (p2.x - p1.x) as f64;
    let dy = (p2.y - p1.y) as f64;
    (dx * dx + dy * dy).sqrt()
}

impl Point {
    /// Create a new point
    pub fn new(x: i32, y: i32) -> Self {
        Point { x, y }
    }

    /// Move point by offset
    pub fn translate(&mut self, dx: i32, dy: i32) {
        self.x += dx;
        self.y += dy;
    }
}
