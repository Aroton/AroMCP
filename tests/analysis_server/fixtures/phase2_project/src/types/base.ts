export interface Entity {
    id: number;
    created_at: Date;
    updated_at: Date;
}

export enum Status {
    ACTIVE = 'active',
    INACTIVE = 'inactive',
    PENDING = 'pending'
}