/**
 * Class methods with inheritance for Phase 3 testing.
 * Tests method resolution across inheritance hierarchies.
 */

import { User } from './basic-types';
import { BaseEntity } from './generic-functions';

// Abstract base class with complex method signatures
export abstract class AbstractProcessor<T extends BaseEntity> {
    protected abstract name: string;
    
    constructor(protected config: { debug: boolean; timeout: number }) {}
    
    // Abstract methods to be implemented
    abstract process(entity: T): Promise<T>;
    abstract validate(entity: T): boolean;
    
    // Concrete methods with complex signatures
    async processWithLogging<U extends T>(
        entity: U,
        logger?: (message: string, data: any) => void
    ): Promise<U> {
        const log = logger || console.log;
        
        log('Starting process', { entityId: entity.id, processor: this.name });
        
        try {
            const result = await this.process(entity);
            log('Process completed', { entityId: result.id });
            return result as U;
        } catch (error) {
            log('Process failed', { entityId: entity.id, error });
            throw error;
        }
    }
    
    batchProcess<U extends T>(
        entities: U[],
        options?: {
            parallel?: boolean;
            batchSize?: number;
            onProgress?: (completed: number, total: number) => void;
        }
    ): Promise<U[]> {
        const opts = {
            parallel: true,
            batchSize: 10,
            ...options
        };
        
        if (opts.parallel) {
            return this.processBatchParallel(entities, opts);
        } else {
            return this.processBatchSequential(entities, opts);
        }
    }
    
    private async processBatchParallel<U extends T>(
        entities: U[],
        options: { batchSize: number; onProgress?: (completed: number, total: number) => void }
    ): Promise<U[]> {
        const results: U[] = [];
        
        for (let i = 0; i < entities.length; i += options.batchSize) {
            const batch = entities.slice(i, i + options.batchSize);
            const batchResults = await Promise.all(
                batch.map(entity => this.process(entity) as Promise<U>)
            );
            
            results.push(...batchResults);
            
            if (options.onProgress) {
                options.onProgress(results.length, entities.length);
            }
        }
        
        return results;
    }
    
    private async processBatchSequential<U extends T>(
        entities: U[],
        options: { onProgress?: (completed: number, total: number) => void }
    ): Promise<U[]> {
        const results: U[] = [];
        
        for (const entity of entities) {
            const result = await this.process(entity) as U;
            results.push(result);
            
            if (options.onProgress) {
                options.onProgress(results.length, entities.length);
            }
        }
        
        return results;
    }
    
    // Method with generic constraints and conditional return types
    transformAndProcess<U extends T, K extends keyof U>(
        entity: U,
        transformKey: K,
        transformer: (value: U[K]) => U[K]
    ): Promise<U> {
        const transformed = { ...entity };
        transformed[transformKey] = transformer(entity[transformKey]);
        return this.process(transformed) as Promise<U>;
    }
}

// Concrete implementation with additional methods
export class UserProcessor extends AbstractProcessor<User> {
    protected name = 'UserProcessor';
    
    constructor(
        config: { debug: boolean; timeout: number },
        private emailService?: {
            sendWelcome: (email: string) => Promise<boolean>;
            sendNotification: (email: string, message: string) => Promise<boolean>;
        }
    ) {
        super(config);
    }
    
    // Implementation of abstract methods
    async process(user: User): Promise<User> {
        if (!this.validate(user)) {
            throw new Error('User validation failed');
        }
        
        // Simulate processing
        await new Promise(resolve => setTimeout(resolve, 100));
        
        const processedUser = {
            ...user,
            name: user.name.trim(),
            email: user.email.toLowerCase()
        };
        
        if (this.emailService && user.isActive) {
            await this.emailService.sendWelcome(processedUser.email);
        }
        
        return processedUser;
    }
    
    validate(user: User): boolean {
        return !!(
            user.id &&
            user.name?.trim() &&
            user.email?.includes('@') &&
            typeof user.isActive === 'boolean'
        );
    }
    
    // Additional methods specific to UserProcessor
    async processNewUser(
        userData: Omit<User, 'id'>,
        sendWelcomeEmail: boolean = true
    ): Promise<User> {
        const user: User = {
            id: Date.now(),
            ...userData
        };
        
        const processedUser = await this.process(user);
        
        if (sendWelcomeEmail && this.emailService) {
            await this.emailService.sendWelcome(processedUser.email);
        }
        
        return processedUser;
    }
    
    async updateUserProfile<K extends keyof User>(
        userId: number,
        field: K,
        value: User[K],
        notifyUser: boolean = false
    ): Promise<User | null> {
        // Simulate fetching user
        const existingUser: User | null = {
            id: userId,
            name: 'Test User',
            email: 'test@example.com',
            isActive: true
        };
        
        if (!existingUser) return null;
        
        const updatedUser = { ...existingUser, [field]: value };
        const processedUser = await this.process(updatedUser);
        
        if (notifyUser && this.emailService) {
            await this.emailService.sendNotification(
                processedUser.email,
                `Your ${String(field)} has been updated`
            );
        }
        
        return processedUser;
    }
    
    // Method with complex generic constraints
    async processUserBatch<T extends User & { priority?: number }>(
        users: T[],
        priorityProcessor?: (user: T) => Promise<T>
    ): Promise<T[]> {
        // Sort by priority if present
        const sortedUsers = users.sort((a, b) => 
            (b.priority || 0) - (a.priority || 0)
        );
        
        const results: T[] = [];
        
        for (const user of sortedUsers) {
            let processedUser: T;
            
            if (user.priority && user.priority > 5 && priorityProcessor) {
                processedUser = await priorityProcessor(user);
            } else {
                processedUser = await this.process(user) as T;
            }
            
            results.push(processedUser);
        }
        
        return results;
    }
}

// Multi-level inheritance with method overriding
export class AdminUserProcessor extends UserProcessor {
    protected name = 'AdminUserProcessor';
    
    constructor(
        config: { debug: boolean; timeout: number },
        emailService?: {
            sendWelcome: (email: string) => Promise<boolean>;
            sendNotification: (email: string, message: string) => Promise<boolean>;
        },
        private auditService?: {
            logAction: (action: string, userId: number, details: any) => Promise<void>;
        }
    ) {
        super(config, emailService);
    }
    
    // Override parent method with additional functionality
    async process(user: User): Promise<User> {
        // Call parent implementation
        const processedUser = await super.process(user);
        
        // Additional admin-specific processing
        if (this.auditService) {
            await this.auditService.logAction('user_processed', processedUser.id, {
                processor: this.name,
                timestamp: new Date().toISOString()
            });
        }
        
        return processedUser;
    }
    
    // Override validation with stricter rules
    validate(user: User): boolean {
        const basicValidation = super.validate(user);
        
        // Additional admin validation
        return basicValidation && 
               user.name.length >= 2 &&
               user.email.length >= 5;
    }
    
    // New methods specific to admin processing
    async processAdminAction(
        adminId: number,
        action: string,
        targetUserId?: number,
        details?: Record<string, any>
    ): Promise<{ success: boolean; auditId?: string }> {
        if (this.auditService) {
            await this.auditService.logAction(action, adminId, {
                targetUserId,
                details,
                timestamp: new Date().toISOString()
            });
            
            return { success: true, auditId: `audit_${Date.now()}` };
        }
        
        return { success: true };
    }
    
    async batchProcessWithAudit<T extends User>(
        users: T[],
        adminId: number,
        reason: string
    ): Promise<{ processed: T[]; auditIds: string[] }> {
        const auditIds: string[] = [];
        
        // Log batch start
        if (this.auditService) {
            await this.auditService.logAction('batch_process_start', adminId, {
                userCount: users.length,
                reason
            });
            auditIds.push(`batch_start_${Date.now()}`);
        }
        
        const processed = await this.batchProcess(users);
        
        // Log batch completion
        if (this.auditService) {
            await this.auditService.logAction('batch_process_complete', adminId, {
                processedCount: processed.length,
                reason
            });
            auditIds.push(`batch_complete_${Date.now()}`);
        }
        
        return { processed, auditIds };
    }
}

// Mixin pattern with multiple inheritance-like behavior
export interface Timestampable {
    createdAt: Date;
    updatedAt: Date;
}

export interface Cacheable<T> {
    getCacheKey(): string;
    fromCache(data: any): T;
    toCache(): any;
}

// Class implementing multiple interfaces
export class CacheableUserProcessor extends UserProcessor implements Cacheable<User> {
    private cache = new Map<string, { data: any; timestamp: number }>();
    
    getCacheKey(): string {
        return `user_processor_${this.constructor.name}`;
    }
    
    fromCache(data: any): User {
        return {
            id: data.id,
            name: data.name,
            email: data.email,
            isActive: data.isActive
        };
    }
    
    toCache(): any {
        return {
            processorName: this.name,
            config: this.config,
            timestamp: Date.now()
        };
    }
    
    async processWithCache(user: User): Promise<User> {
        const cacheKey = `user_${user.id}`;
        const cached = this.cache.get(cacheKey);
        
        if (cached && Date.now() - cached.timestamp < 300000) { // 5 minutes
            return this.fromCache(cached.data);
        }
        
        const processed = await this.process(user);
        
        this.cache.set(cacheKey, {
            data: this.processedUserToCache(processed),
            timestamp: Date.now()
        });
        
        return processed;
    }
    
    private processedUserToCache(user: User): any {
        return {
            id: user.id,
            name: user.name,
            email: user.email,
            isActive: user.isActive,
            processed: true
        };
    }
    
    // Method with complex generic method chaining
    async chainProcess<T extends User, U>(
        user: T,
        ...processors: Array<(user: T) => Promise<T> | T>
    ): Promise<T> {
        let current = user;
        
        for (const processor of processors) {
            current = await Promise.resolve(processor(current));
        }
        
        return this.processWithCache(current) as Promise<T>;
    }
}

// Static method class for utility functions
export class UserProcessorUtils {
    static createDefaultConfig(): { debug: boolean; timeout: number } {
        return { debug: false, timeout: 5000 };
    }
    
    static async validateProcessorChain<T extends AbstractProcessor<User>>(
        processors: T[]
    ): Promise<{ valid: boolean; errors: string[] }> {
        const errors: string[] = [];
        
        for (let i = 0; i < processors.length; i++) {
            try {
                // Test with a mock user
                const testUser: User = {
                    id: 999,
                    name: 'Test User',
                    email: 'test@example.com',
                    isActive: true
                };
                
                await processors[i].validate(testUser);
            } catch (error) {
                errors.push(`Processor ${i}: ${error instanceof Error ? error.message : 'Unknown error'}`);
            }
        }
        
        return { valid: errors.length === 0, errors };
    }
    
    static compareProcessors<T extends AbstractProcessor<User>>(
        processor1: T,
        processor2: T,
        testUser: User
    ): Promise<{
        processor1Result: User;
        processor2Result: User;
        difference: Partial<User>;
    }> {
        return Promise.all([
            processor1.process(testUser),
            processor2.process(testUser)
        ]).then(([result1, result2]) => {
            const difference: Partial<User> = {};
            
            for (const key in result1) {
                if (result1[key as keyof User] !== result2[key as keyof User]) {
                    difference[key as keyof User] = result2[key as keyof User];
                }
            }
            
            return {
                processor1Result: result1,
                processor2Result: result2,
                difference
            };
        });
    }
}