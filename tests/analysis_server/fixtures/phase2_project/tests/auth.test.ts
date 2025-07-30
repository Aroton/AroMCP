import { AuthService } from '../src/auth/auth-service';
import { AuthenticatedUser, GuestUser } from '../src/auth/user';
import { UserRole } from '../src/types/user';

describe('AuthService', () => {
    let authService: AuthService;
    
    beforeEach(() => {
        authService = new AuthService();
    });
    
    test('should create guest user', () => {
        const guest = authService.createGuestUser('Test Guest');
        expect(guest).toBeInstanceOf(GuestUser);
        expect(guest.getName()).toBe('Test Guest');
    });
    
    test('should authenticate user', async () => {
        const user = await authService.authenticate('test@example.com', 'password123');
        expect(user).toBeInstanceOf(AuthenticatedUser);
    });
});