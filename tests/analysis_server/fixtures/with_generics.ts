// TypeScript file with generics for testing
export interface Repository<T> {
    findById(id: string): Promise<T | null>;
    save(entity: T): Promise<T>;
    delete(id: string): Promise<boolean>;
}

export class InMemoryRepository<T extends { id: string }> implements Repository<T> {
    private items: Map<string, T> = new Map();
    
    async findById(id: string): Promise<T | null> {
        return this.items.get(id) || null;
    }
    
    async save(entity: T): Promise<T> {
        this.items.set(entity.id, entity);
        return entity;
    }
    
    async delete(id: string): Promise<boolean> {
        return this.items.delete(id);
    }
    
    getAll(): T[] {
        return Array.from(this.items.values());
    }
}

export type ApiResponse<T> = {
    success: boolean;
    data?: T;
    error?: string;
};

export function createResponse<T>(data: T): ApiResponse<T> {
    return {
        success: true,
        data
    };
}

export function createErrorResponse<T>(error: string): ApiResponse<T> {
    return {
        success: false,
        error
    };
}