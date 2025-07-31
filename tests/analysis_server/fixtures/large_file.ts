// Large TypeScript file for performance testing
// This file contains many classes and functions to test parsing performance

export interface BaseEntity {
    id: string;
    createdAt: Date;
    updatedAt: Date;
}

export interface User extends BaseEntity {
    name: string;
    email: string;
    isActive: boolean;
}

export interface Product extends BaseEntity {
    name: string;
    price: number;
    category: string;
    inStock: boolean;
}

export interface Order extends BaseEntity {
    userId: string;
    productIds: string[];
    totalAmount: number;
    status: 'pending' | 'confirmed' | 'shipped' | 'delivered';
}

export class UserRepository {
    private users: Map<string, User> = new Map();
    
    async findById(id: string): Promise<User | null> {
        return this.users.get(id) || null;
    }
    
    async findByEmail(email: string): Promise<User | null> {
        for (const user of this.users.values()) {
            if (user.email === email) {
                return user;
            }
        }
        return null;
    }
    
    async save(user: User): Promise<User> {
        this.users.set(user.id, user);
        return user;
    }
    
    async delete(id: string): Promise<boolean> {
        return this.users.delete(id);
    }
    
    async findAll(): Promise<User[]> {
        return Array.from(this.users.values());
    }
    
    async findActiveUsers(): Promise<User[]> {
        return Array.from(this.users.values()).filter(user => user.isActive);
    }
}

export class ProductRepository {
    private products: Map<string, Product> = new Map();
    
    async findById(id: string): Promise<Product | null> {
        return this.products.get(id) || null;
    }
    
    async findByCategory(category: string): Promise<Product[]> {
        return Array.from(this.products.values()).filter(p => p.category === category);
    }
    
    async save(product: Product): Promise<Product> {
        this.products.set(product.id, product);
        return product;
    }
    
    async delete(id: string): Promise<boolean> {
        return this.products.delete(id);
    }
    
    async findInStock(): Promise<Product[]> {
        return Array.from(this.products.values()).filter(p => p.inStock);
    }
}

export class OrderRepository {
    private orders: Map<string, Order> = new Map();
    
    async findById(id: string): Promise<Order | null> {
        return this.orders.get(id) || null;
    }
    
    async findByUserId(userId: string): Promise<Order[]> {
        return Array.from(this.orders.values()).filter(o => o.userId === userId);
    }
    
    async save(order: Order): Promise<Order> {
        this.orders.set(order.id, order);
        return order;
    }
    
    async delete(id: string): Promise<boolean> {
        return this.orders.delete(id);
    }
    
    async findByStatus(status: Order['status']): Promise<Order[]> {
        return Array.from(this.orders.values()).filter(o => o.status === status);
    }
}

export class UserService {
    constructor(private userRepo: UserRepository) {}
    
    async createUser(name: string, email: string): Promise<User> {
        const user: User = {
            id: this.generateId(),
            name,
            email,
            isActive: true,
            createdAt: new Date(),
            updatedAt: new Date()
        };
        return this.userRepo.save(user);
    }
    
    async getUserById(id: string): Promise<User | null> {
        return this.userRepo.findById(id);
    }
    
    async getUserByEmail(email: string): Promise<User | null> {
        return this.userRepo.findByEmail(email);
    }
    
    async updateUser(id: string, updates: Partial<User>): Promise<User | null> {
        const user = await this.userRepo.findById(id);
        if (!user) return null;
        
        const updatedUser = { ...user, ...updates, updatedAt: new Date() };
        return this.userRepo.save(updatedUser);
    }
    
    async deleteUser(id: string): Promise<boolean> {
        return this.userRepo.delete(id);
    }
    
    async activateUser(id: string): Promise<User | null> {
        return this.updateUser(id, { isActive: true });
    }
    
    async deactivateUser(id: string): Promise<User | null> {
        return this.updateUser(id, { isActive: false });
    }
    
    private generateId(): string {
        return Math.random().toString(36).substr(2, 9);
    }
}

export class ProductService {
    constructor(private productRepo: ProductRepository) {}
    
    async createProduct(name: string, price: number, category: string): Promise<Product> {
        const product: Product = {
            id: this.generateId(),
            name,
            price,
            category,
            inStock: true,
            createdAt: new Date(),
            updatedAt: new Date()
        };
        return this.productRepo.save(product);
    }
    
    async getProductById(id: string): Promise<Product | null> {
        return this.productRepo.findById(id);
    }
    
    async getProductsByCategory(category: string): Promise<Product[]> {
        return this.productRepo.findByCategory(category);
    }
    
    async updateProduct(id: string, updates: Partial<Product>): Promise<Product | null> {
        const product = await this.productRepo.findById(id);
        if (!product) return null;
        
        const updatedProduct = { ...product, ...updates, updatedAt: new Date() };
        return this.productRepo.save(updatedProduct);
    }
    
    async deleteProduct(id: string): Promise<boolean> {
        return this.productRepo.delete(id);
    }
    
    async markInStock(id: string): Promise<Product | null> {
        return this.updateProduct(id, { inStock: true });
    }
    
    async markOutOfStock(id: string): Promise<Product | null> {
        return this.updateProduct(id, { inStock: false });
    }
    
    private generateId(): string {
        return Math.random().toString(36).substr(2, 9);
    }
}

export class OrderService {
    constructor(
        private orderRepo: OrderRepository,
        private userService: UserService,
        private productService: ProductService
    ) {}
    
    async createOrder(userId: string, productIds: string[]): Promise<Order | null> {
        const user = await this.userService.getUserById(userId);
        if (!user || !user.isActive) return null;
        
        const products = await Promise.all(
            productIds.map(id => this.productService.getProductById(id))
        );
        
        if (products.some(p => !p || !p.inStock)) return null;
        
        const totalAmount = products.reduce((sum, p) => sum + (p?.price || 0), 0);
        
        const order: Order = {
            id: this.generateId(),
            userId,
            productIds,
            totalAmount,
            status: 'pending',
            createdAt: new Date(),
            updatedAt: new Date()
        };
        
        return this.orderRepo.save(order);
    }
    
    async getOrderById(id: string): Promise<Order | null> {
        return this.orderRepo.findById(id);
    }
    
    async getOrdersByUserId(userId: string): Promise<Order[]> {
        return this.orderRepo.findByUserId(userId);
    }
    
    async updateOrderStatus(id: string, status: Order['status']): Promise<Order | null> {
        const order = await this.orderRepo.findById(id);
        if (!order) return null;
        
        const updatedOrder = { ...order, status, updatedAt: new Date() };
        return this.orderRepo.save(updatedOrder);
    }
    
    async confirmOrder(id: string): Promise<Order | null> {
        return this.updateOrderStatus(id, 'confirmed');
    }
    
    async shipOrder(id: string): Promise<Order | null> {
        return this.updateOrderStatus(id, 'shipped');
    }
    
    async deliverOrder(id: string): Promise<Order | null> {
        return this.updateOrderStatus(id, 'delivered');
    }
    
    private generateId(): string {
        return Math.random().toString(36).substr(2, 9);
    }
}

// Utility functions
export function validateEmail(email: string): boolean {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

export function formatPrice(price: number): string {
    return `$${price.toFixed(2)}`;
}

export function formatDate(date: Date): string {
    return date.toISOString().split('T')[0];
}

export function calculateTax(amount: number, rate: number = 0.08): number {
    return amount * rate;
}

export function calculateTotal(amount: number, taxRate: number = 0.08): number {
    return amount + calculateTax(amount, taxRate);
}

// Constants
export const DEFAULT_TAX_RATE = 0.08;
export const MAX_ORDER_ITEMS = 50;
export const MIN_ORDER_AMOUNT = 10.00;

// Type guards
export function isUser(obj: any): obj is User {
    return obj && typeof obj.id === 'string' && typeof obj.name === 'string' && typeof obj.email === 'string';
}

export function isProduct(obj: any): obj is Product {
    return obj && typeof obj.id === 'string' && typeof obj.name === 'string' && typeof obj.price === 'number';
}

export function isOrder(obj: any): obj is Order {
    return obj && typeof obj.id === 'string' && typeof obj.userId === 'string' && Array.isArray(obj.productIds);
}