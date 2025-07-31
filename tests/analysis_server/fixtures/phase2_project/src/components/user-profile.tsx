import React, { useState, useEffect } from 'react';
import { User, UserProfile } from '../types/user';
import { AuthService } from '../auth/auth-service';
import { AuthenticatedUser } from '../auth/user';

interface UserProfileProps {
    user: User;
    authService: AuthService;
}

export const UserProfileComponent: React.FC<UserProfileProps> = ({ user, authService }) => {
    const [profile, setProfile] = useState<UserProfile | null>(user.profile || null);
    const [isEditing, setIsEditing] = useState(false);
    
    useEffect(() => {
        loadUserProfile();
    }, [user.id]);
    
    const loadUserProfile = async (): Promise<void> => {
        // Mock profile loading
        if (user.profile) {
            setProfile(user.profile);
        }
    };
    
    const handleSaveProfile = async (updatedProfile: UserProfile): Promise<void> => {
        const currentUser = authService.getCurrentUser();
        if (currentUser instanceof AuthenticatedUser) {
            currentUser.setProfile(updatedProfile);
            setProfile(updatedProfile);
            setIsEditing(false);
        }
    };
    
    const renderProfileEditor = (): JSX.Element => {
        return (
            <div className="profile-editor">
                <input 
                    value={profile?.bio || ''} 
                    onChange={e => profile && setProfile({...profile, bio: e.target.value})}
                />
                <button onClick={() => profile && handleSaveProfile(profile)}>
                    Save Profile
                </button>
            </div>
        );
    };
    
    return (
        <div className="user-profile">
            <h2>{user.name}</h2>
            <p>{user.email}</p>
            {profile && (
                <div>
                    <img src={profile.avatar} alt="Avatar" />
                    <p>{profile.bio}</p>
                    <div>Theme: {profile.preferences.theme}</div>
                </div>
            )}
            {isEditing ? renderProfileEditor() : (
                <button onClick={() => setIsEditing(true)}>Edit Profile</button>
            )}
        </div>
    );
};