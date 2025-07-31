// Class methods and object-oriented patterns for call graph testing

export class UserService {
    private database: Database;
    private cache: CacheService;
    private logger: LoggerService;
    
    constructor(database: Database, cache: CacheService, logger: LoggerService) {
        this.database = database;
        this.cache = cache;
        this.logger = logger;
    }
    
    // Public method with multiple call paths
    public async createUser(userData: UserData): Promise<User> {
        this.logger.info('Creating new user');
        
        // Validation calls
        await this.validateUserData(userData);
        const normalizedData = this.normalizeUserData(userData);
        
        // Check for existing user
        const existingUser = await this.findUserByEmail(normalizedData.email);
        if (existingUser) {
            throw new Error('User already exists');
        }
        
        // Create user
        const hashedPassword = await this.hashPassword(normalizedData.password);
        const user = await this.database.createUser({
            ...normalizedData,
            password: hashedPassword
        });
        
        // Post-creation tasks
        await this.sendWelcomeEmail(user);
        await this.cache.invalidateUserCache(user.email);
        this.logger.info(`User created: ${user.id}`);
        
        return user;
    }
    
    // Method calling other methods in the same class
    public async updateUser(userId: string, updates: Partial<UserData>): Promise<User> {
        const user = await this.getUserById(userId);
        if (!user) {
            throw new Error('User not found');
        }
        
        // Conditional method calls based on what's being updated
        if (updates.email) {
            await this.validateEmailUpdate(updates.email, user);
        }
        
        if (updates.password) {
            updates.password = await this.hashPassword(updates.password);
            await this.invalidateUserSessions(userId);
        }
        
        const updatedUser = await this.database.updateUser(userId, updates);
        await this.cache.updateUserCache(updatedUser);
        
        return updatedUser;
    }
    
    // Method with complex conditional logic
    public async authenticateUser(email: string, password: string): Promise<AuthResult> {
        const user = await this.findUserByEmail(email);
        if (!user) {
            await this.logFailedAttempt(email, 'user_not_found');
            return { success: false, reason: 'Invalid credentials' };
        }
        
        if (user.isLocked) {
            await this.logFailedAttempt(email, 'account_locked');
            return { success: false, reason: 'Account locked' };
        }
        
        const isValidPassword = await this.verifyPassword(password, user.password);
        if (!isValidPassword) {
            await this.handleFailedLogin(user);
            return { success: false, reason: 'Invalid credentials' };
        }
        
        // Success path
        await this.handleSuccessfulLogin(user);
        const token = await this.generateAuthToken(user);
        
        return { success: true, token, user };
    }
    
    // Private helper methods
    private async validateUserData(userData: UserData): Promise<void> {
        if (!this.isValidEmail(userData.email)) {
            throw new Error('Invalid email format');
        }
        
        if (!this.isValidPassword(userData.password)) {
            throw new Error('Invalid password format');
        }
        
        await this.checkPasswordStrength(userData.password);
    }
    
    private normalizeUserData(userData: UserData): UserData {
        return {
            ...userData,
            email: userData.email.toLowerCase().trim(),
            firstName: this.capitalizeFirst(userData.firstName),
            lastName: this.capitalizeFirst(userData.lastName)
        };
    }
    
    private async findUserByEmail(email: string): Promise<User | null> {
        // Check cache first
        const cachedUser = await this.cache.getUserByEmail(email);
        if (cachedUser) {
            return cachedUser;
        }
        
        // Query database
        const user = await this.database.findUserByEmail(email);
        if (user) {
            await this.cache.setUserCache(user);
        }
        
        return user;
    }
    
    private async getUserById(userId: string): Promise<User | null> {
        const cachedUser = await this.cache.getUserById(userId);
        if (cachedUser) {
            return cachedUser;
        }
        
        const user = await this.database.findUserById(userId);
        if (user) {
            await this.cache.setUserCache(user);
        }
        
        return user;
    }
    
    private async hashPassword(password: string): Promise<string> {
        const salt = await this.generateSalt();
        return await this.computeHash(password, salt);
    }
    
    private async verifyPassword(password: string, hashedPassword: string): Promise<boolean> {
        const computedHash = await this.computeHash(password, this.extractSalt(hashedPassword));
        return computedHash === hashedPassword;
    }
    
    private async handleFailedLogin(user: User): Promise<void> {
        user.failedLoginAttempts++;
        
        if (user.failedLoginAttempts >= 5) {
            await this.lockUserAccount(user);
        }
        
        await this.database.updateUser(user.id, { 
            failedLoginAttempts: user.failedLoginAttempts,
            lastFailedLogin: new Date()
        });
        
        await this.logFailedAttempt(user.email, 'invalid_password');
    }
    
    private async handleSuccessfulLogin(user: User): Promise<void> {
        await this.database.updateUser(user.id, {
            lastLogin: new Date(),
            failedLoginAttempts: 0
        });
        
        await this.logSuccessfulLogin(user);
    }
    
    // Method calling static methods
    private isValidEmail(email: string): boolean {
        return EmailValidator.isValid(email);
    }
    
    private isValidPassword(password: string): boolean {
        return PasswordValidator.isValid(password);
    }
    
    private capitalizeFirst(text: string): string {
        return StringUtils.capitalizeFirst(text);
    }
    
    // Method with multiple async operations
    private async validateEmailUpdate(newEmail: string, currentUser: User): Promise<void> {
        if (!this.isValidEmail(newEmail)) {
            throw new Error('Invalid email format');
        }
        
        const existingUser = await this.findUserByEmail(newEmail);
        if (existingUser && existingUser.id !== currentUser.id) {
            throw new Error('Email already in use');
        }
        
        await this.sendEmailChangeNotification(currentUser, newEmail);
    }
    
    private async generateAuthToken(user: User): Promise<string> {
        const payload = this.createTokenPayload(user);
        return await TokenService.generateToken(payload);
    }
    
    private createTokenPayload(user: User): TokenPayload {
        return {
            userId: user.id,
            email: user.email,
            role: user.role,
            issuedAt: Date.now()
        };
    }
    
    // Additional helper methods for complete call graph
    private async generateSalt(): Promise<string> { return 'salt'; }
    private async computeHash(password: string, salt: string): Promise<string> { return 'hash'; }
    private extractSalt(hashedPassword: string): string { return 'salt'; }
    private async checkPasswordStrength(password: string): Promise<void> { }
    private async sendWelcomeEmail(user: User): Promise<void> { }
    private async sendEmailChangeNotification(user: User, newEmail: string): Promise<void> { }
    private async invalidateUserSessions(userId: string): Promise<void> { }
    private async lockUserAccount(user: User): Promise<void> { }
    private async logFailedAttempt(email: string, reason: string): Promise<void> { }
    private async logSuccessfulLogin(user: User): Promise<void> { }
}

// Static method calls and inheritance patterns
export class BaseEntity {
    protected id: string;
    protected createdAt: Date;
    protected updatedAt: Date;
    
    constructor(id: string) {
        this.id = id;
        this.createdAt = new Date();
        this.updatedAt = new Date();
    }
    
    // Base method that calls other methods
    public save(): Promise<void> {
        this.validate();
        this.updateTimestamp();
        return this.persistToDatabase();
    }
    
    protected validate(): void {
        if (!this.id) {
            throw new Error('ID is required');
        }
    }
    
    protected updateTimestamp(): void {
        this.updatedAt = new Date();
    }
    
    protected async persistToDatabase(): Promise<void> {
        // Will be overridden by subclasses
        throw new Error('Must be implemented by subclass');
    }
    
    // Static factory method
    public static create<T extends BaseEntity>(this: new (id: string) => T, id: string): T {
        const instance = new this(id);
        instance.initialize();
        return instance;
    }
    
    protected initialize(): void {
        // Base initialization
    }
}

export class OrderEntity extends BaseEntity {
    private items: OrderItem[];
    private total: number;
    
    constructor(id: string, items: OrderItem[]) {
        super(id); // Calls parent constructor
        this.items = items;
        this.total = 0;
    }
    
    // Overridden method that calls parent and additional methods
    protected validate(): void {
        super.validate(); // Calls parent method
        this.validateItems();
        this.validateTotal();
    }
    
    // Method calling multiple other methods in sequence
    public calculateTotal(): number {
        let total = 0;
        
        for (const item of this.items) {
            total += this.calculateItemTotal(item);
        }
        
        total = this.applyDiscounts(total);
        total = this.addTaxes(total);
        
        this.total = total;
        return total;
    }
    
    // Method with conditional calls to other methods
    public processOrder(): Promise<OrderResult> {
        this.validateForProcessing();
        
        if (this.requiresPayment()) {
            return this.processWithPayment();
        } else {
            return this.processWithoutPayment();
        }
    }
    
    // Overridden base method
    protected async persistToDatabase(): Promise<void> {
        await this.saveOrderData();
        await this.saveOrderItems();
        await this.updateInventory();
    }
    
    // Static method calling instance methods
    public static async createFromCart(cartId: string): Promise<OrderEntity> {
        const cartItems = await CartService.getCartItems(cartId);
        const order = new OrderEntity(this.generateOrderId(), cartItems);
        order.calculateTotal();
        await order.save();
        return order;
    }
    
    private validateItems(): void {
        if (!this.items || this.items.length === 0) {
            throw new Error('Order must have items');
        }
        
        this.items.forEach(item => this.validateItem(item));
    }
    
    private validateTotal(): void {
        if (this.total < 0) {
            throw new Error('Total cannot be negative');
        }
    }
    
    private validateItem(item: OrderItem): void {
        if (!item.productId) {
            throw new Error('Item must have product ID');
        }
        if (item.quantity <= 0) {
            throw new Error('Item quantity must be positive');
        }
    }
    
    private calculateItemTotal(item: OrderItem): number {
        return item.price * item.quantity;
    }
    
    private applyDiscounts(total: number): number {
        let discountedTotal = total;
        
        if (this.hasVolumeDiscount()) {
            discountedTotal = this.applyVolumeDiscount(discountedTotal);
        }
        
        if (this.hasCoupon()) {
            discountedTotal = this.applyCouponDiscount(discountedTotal);
        }
        
        return discountedTotal;
    }
    
    private addTaxes(total: number): number {
        const taxRate = this.getTaxRate();
        return total * (1 + taxRate);
    }
    
    private validateForProcessing(): void {
        this.validate();
        if (this.total === 0) {
            this.calculateTotal();
        }
    }
    
    private requiresPayment(): boolean {
        return this.total > 0;
    }
    
    private async processWithPayment(): Promise<OrderResult> {
        const paymentResult = await this.processPayment();
        if (paymentResult.success) {
            await this.fulfillOrder();
            await this.sendConfirmationEmail();
            return { success: true, orderId: this.id };
        } else {
            await this.handlePaymentFailure(paymentResult);
            return { success: false, error: paymentResult.error };
        }
    }
    
    private async processWithoutPayment(): Promise<OrderResult> {
        await this.fulfillOrder();
        await this.sendConfirmationEmail();
        return { success: true, orderId: this.id };
    }
    
    // Additional private methods for complete call graph
    private static generateOrderId(): string { return 'order_' + Date.now(); }
    private hasVolumeDiscount(): boolean { return this.items.length > 10; }
    private hasCoupon(): boolean { return false; }
    private applyVolumeDiscount(total: number): number { return total * 0.9; }
    private applyCouponDiscount(total: number): number { return total * 0.95; }
    private getTaxRate(): number { return 0.08; }
    private async processPayment(): Promise<PaymentResult> { return { success: true }; }
    private async fulfillOrder(): Promise<void> { }
    private async sendConfirmationEmail(): Promise<void> { }
    private async handlePaymentFailure(result: PaymentResult): Promise<void> { }
    private async saveOrderData(): Promise<void> { }
    private async saveOrderItems(): Promise<void> { }
    private async updateInventory(): Promise<void> { }
}

// Method chaining patterns
export class QueryBuilder {
    private query: QueryConfig = {};
    
    public select(fields: string[]): QueryBuilder {
        this.query.select = fields;
        return this;
    }
    
    public from(table: string): QueryBuilder {
        this.query.from = table;
        return this;
    }
    
    public where(condition: string): QueryBuilder {
        if (!this.query.where) {
            this.query.where = [];
        }
        this.query.where.push(condition);
        return this;
    }
    
    public join(table: string, condition: string): QueryBuilder {
        if (!this.query.joins) {
            this.query.joins = [];
        }
        this.query.joins.push({ table, condition });
        return this;
    }
    
    public orderBy(field: string, direction: 'ASC' | 'DESC' = 'ASC'): QueryBuilder {
        if (!this.query.orderBy) {
            this.query.orderBy = [];
        }
        this.query.orderBy.push({ field, direction });
        return this;
    }
    
    public limit(count: number): QueryBuilder {
        this.query.limit = count;
        return this;
    }
    
    // Terminal method that executes the query
    public async execute<T>(): Promise<T[]> {
        this.validateQuery();
        const sqlQuery = this.buildSqlQuery();
        return await this.executeQuery<T>(sqlQuery);
    }
    
    // Terminal method that returns count
    public async count(): Promise<number> {
        this.validateQuery();
        const countQuery = this.buildCountQuery();
        const result = await this.executeQuery<{ count: number }>(countQuery);
        return result[0].count;
    }
    
    private validateQuery(): void {
        if (!this.query.from) {
            throw new Error('FROM clause is required');
        }
        if (!this.query.select || this.query.select.length === 0) {
            throw new Error('SELECT clause is required');
        }
    }
    
    private buildSqlQuery(): string {
        let sql = `SELECT ${this.query.select!.join(', ')} FROM ${this.query.from}`;
        
        if (this.query.joins) {
            sql += this.buildJoinClause();
        }
        
        if (this.query.where) {
            sql += this.buildWhereClause();
        }
        
        if (this.query.orderBy) {
            sql += this.buildOrderByClause();
        }
        
        if (this.query.limit) {
            sql += ` LIMIT ${this.query.limit}`;
        }
        
        return sql;
    }
    
    private buildCountQuery(): string {
        let sql = `SELECT COUNT(*) as count FROM ${this.query.from}`;
        
        if (this.query.joins) {
            sql += this.buildJoinClause();
        }
        
        if (this.query.where) {
            sql += this.buildWhereClause();
        }
        
        return sql;
    }
    
    private buildJoinClause(): string {
        return this.query.joins!
            .map(join => ` JOIN ${join.table} ON ${join.condition}`)
            .join('');
    }
    
    private buildWhereClause(): string {
        return ` WHERE ${this.query.where!.join(' AND ')}`;
    }
    
    private buildOrderByClause(): string {
        return ` ORDER BY ${this.query.orderBy!
            .map(order => `${order.field} ${order.direction}`)
            .join(', ')}`;
    }
    
    private async executeQuery<T>(sql: string): Promise<T[]> {
        // Mock database execution
        console.log('Executing query:', sql);
        return [];
    }
}

// Static utility classes
export class EmailValidator {
    public static isValid(email: string): boolean {
        return this.hasValidFormat(email) && this.hasValidDomain(email);
    }
    
    private static hasValidFormat(email: string): boolean {
        const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        return emailRegex.test(email);
    }
    
    private static hasValidDomain(email: string): boolean {
        const domain = this.extractDomain(email);
        return this.isValidDomain(domain);
    }
    
    private static extractDomain(email: string): string {
        return email.split('@')[1];
    }
    
    private static isValidDomain(domain: string): boolean {
        // Simple domain validation
        return domain.includes('.') && domain.length > 3;
    }
}

export class PasswordValidator {
    public static isValid(password: string): boolean {
        return this.hasMinLength(password) && 
               this.hasRequiredCharacters(password) &&
               this.isNotCommon(password);
    }
    
    private static hasMinLength(password: string): boolean {
        return password.length >= 8;
    }
    
    private static hasRequiredCharacters(password: string): boolean {
        return this.hasUppercase(password) &&
               this.hasLowercase(password) &&
               this.hasDigit(password) &&
               this.hasSpecialChar(password);
    }
    
    private static hasUppercase(password: string): boolean {
        return /[A-Z]/.test(password);
    }
    
    private static hasLowercase(password: string): boolean {
        return /[a-z]/.test(password);
    }
    
    private static hasDigit(password: string): boolean {
        return /\d/.test(password);
    }
    
    private static hasSpecialChar(password: string): boolean {
        return /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(password);
    }
    
    private static isNotCommon(password: string): boolean {
        const commonPasswords = ['password', '123456', 'password123'];
        return !commonPasswords.includes(password.toLowerCase());
    }
}

export class StringUtils {
    public static capitalizeFirst(text: string): string {
        if (!text) return text;
        return text.charAt(0).toUpperCase() + text.slice(1).toLowerCase();
    }
    
    public static formatName(firstName: string, lastName: string): string {
        const formattedFirst = this.capitalizeFirst(firstName);
        const formattedLast = this.capitalizeFirst(lastName);
        return `${formattedFirst} ${formattedLast}`;
    }
}

export class TokenService {
    public static async generateToken(payload: TokenPayload): Promise<string> {
        const header = this.createHeader();
        const encodedPayload = this.encodePayload(payload);
        const signature = await this.createSignature(header, encodedPayload);
        return `${header}.${encodedPayload}.${signature}`;
    }
    
    private static createHeader(): string {
        return Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64');
    }
    
    private static encodePayload(payload: TokenPayload): string {
        return Buffer.from(JSON.stringify(payload)).toString('base64');
    }
    
    private static async createSignature(header: string, payload: string): string {
        const data = `${header}.${payload}`;
        return this.hmacSha256(data, 'secret');
    }
    
    private static hmacSha256(data: string, secret: string): string {
        // Mock implementation
        return 'signature';
    }
}

export class CartService {
    public static async getCartItems(cartId: string): Promise<OrderItem[]> {
        // Mock implementation
        return [];
    }
}

// Type definitions for testing
interface UserData {
    email: string;
    password: string;
    firstName: string;
    lastName: string;
}

interface User {
    id: string;
    email: string;
    password: string;
    role: string;
    isLocked: boolean;
    failedLoginAttempts: number;
    lastLogin?: Date;
}

interface AuthResult {
    success: boolean;
    reason?: string;
    token?: string;
    user?: User;
}

interface Database {
    createUser(userData: any): Promise<User>;
    updateUser(userId: string, updates: any): Promise<User>;
    findUserByEmail(email: string): Promise<User | null>;
    findUserById(userId: string): Promise<User | null>;
}

interface CacheService {
    getUserByEmail(email: string): Promise<User | null>;
    getUserById(userId: string): Promise<User | null>;
    setUserCache(user: User): Promise<void>;
    updateUserCache(user: User): Promise<void>;
    invalidateUserCache(email: string): Promise<void>;
}

interface LoggerService {
    info(message: string): void;
    error(message: string): void;
}

interface OrderItem {
    productId: string;
    quantity: number;
    price: number;
}

interface OrderResult {
    success: boolean;
    orderId?: string;
    error?: string;
}

interface PaymentResult {
    success: boolean;
    error?: string;
}

interface TokenPayload {
    userId: string;
    email: string;
    role: string;
    issuedAt: number;
}

interface QueryConfig {
    select?: string[];
    from?: string;
    where?: string[];
    joins?: Array<{ table: string; condition: string }>;
    orderBy?: Array<{ field: string; direction: 'ASC' | 'DESC' }>;
    limit?: number;
}