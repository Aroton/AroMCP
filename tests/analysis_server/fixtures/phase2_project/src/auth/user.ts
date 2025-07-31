import { User, UserProfile, UserRole } from '../types/user';

export abstract class BaseUser {
    protected id: number;
    protected name: string;
    
    constructor(id: number, name: string) {
        this.id = id;
        this.name = name;
    }
    
    abstract getDisplayName(): string;
    
    getId(): number {
        return this.id;
    }
    
    getName(): string {
        return this.name;
    }
}

export class AuthenticatedUser extends BaseUser implements User {
    public email: string;
    public profile?: UserProfile;
    private role: UserRole;
    
    constructor(id: number, name: string, email: string, role: UserRole = UserRole.USER) {
        super(id, name);
        this.email = email;
        this.role = role;
    }
    
    getDisplayName(): string {
        return this.profile?.bio ? `${this.name} - ${this.profile.bio}` : this.name;
    }
    
    setProfile(profile: UserProfile): void {
        this.profile = profile;
    }
    
    getRole(): UserRole {
        return this.role;
    }
    
    hasPermission(permission: string): boolean {
        return this.role === UserRole.ADMIN;
    }
}

export class GuestUser extends BaseUser {
    getDisplayName(): string {
        return `Guest: ${this.name}`;
    }
}