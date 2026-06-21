// Demo "auth" model. There is no real authentication — the login screen offers
// two one-tap demo accounts so the flow is structured as if a login is required.

import { ELDER_ID } from '../config';

export type Role = 'caretaker' | 'elder';

export interface DemoUser {
  role: Role;
  /** Display name of the logged-in person. */
  name: string;
  email: string;
  /** The elder this session is concerned with (same resident for both roles). */
  elderId: string;
}

export const DEMO_USERS: Record<Role, DemoUser> = {
  caretaker: {
    role: 'caretaker',
    name: 'Jack',
    email: 'jack@quietcare.app',
    elderId: ELDER_ID,
  },
  elder: {
    role: 'elder',
    name: 'Margaret',
    email: 'margaret@quietcare.app',
    elderId: ELDER_ID,
  },
};
