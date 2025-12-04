/**
 * Sample TypeScript module for testing code parsing.
 */

/**
 * Interface for user data
 */
export interface User {
    id: number;
    name: string;
    email: string;
}

/**
 * Calculate sum of two numbers
 */
export function add(a: number, b: number): number {
    return a + b;
}

/**
 * User service class
 */
export class UserService {
    private users: User[] = [];

    /**
     * Add a new user
     */
    addUser(user: User): void {
        if (this.users.find(u => u.id === user.id)) {
            throw new Error("User already exists");
        }
        this.users.push(user);
    }

    /**
     * Find user by ID
     */
    findUser(id: number): User | undefined {
        return this.users.find(u => u.id === id);
    }
}
