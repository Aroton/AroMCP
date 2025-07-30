// TypeScript file with imports for testing
import { User, UserService } from './valid_typescript';
import { Repository } from './with_generics';
import * as utils from './utils/helpers';

export interface UserRepository extends Repository<User> {
    findByEmail(email: string): Promise<User | null>;
}

export class DatabaseUserRepository implements UserRepository {
    constructor(private userService: UserService) {}
    
    async findById(id: string): Promise<User | null> {
        const numericId = parseInt(id, 10);
        return this.userService.findById(numericId);
    }
    
    async findByEmail(email: string): Promise<User | null> {
        // Mock implementation
        return null;
    }
    
    async save(user: User): Promise<User> {
        this.userService.create(user);
        return user;
    }
    
    async delete(id: string): Promise<boolean> {
        // Mock implementation
        return true;
    }
}

export function processUser(user: User): string {
    return utils.formatName(user.name);
}

// Dynamic import example
export async function loadConfig(): Promise<any> {
    const config = await import('./config.json');
    return config.default;
}