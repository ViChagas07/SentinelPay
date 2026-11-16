import { authUserSchema, type AuthUser } from "./auth";

export const userProfileSchema = authUserSchema;

export type UserProfile = AuthUser;
