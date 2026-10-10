# ADR-019 — Investigate mature OIDC integration without shipping a pretend login

- **Date:** 2026-10-10
- **Status:** DESIGN ONLY for product authentication; offline library spike is separately testable.
- **Owner:** Developer; provider and security-sensitive deployment choice remain open.
- **Master-plan references:** §§9.2, 10.1, 17 P0/P3; DEC-133/134.
- **Problem and constraints:** Phase 0 calls for an auth spike, while complete identities, memberships and RBAC belong to Phase 3. No OIDC issuer, application registration or deployment origin has been supplied.
- **Decision:** Exercise installed Authlib's authorization-code/PKCE/state primitives offline. Keep all Phase 0 product routes absent and development bindings on loopback. Proposed later integration uses a mature OIDC provider plus server-owned sessions with secure HttpOnly/SameSite cookies; no JWT or password implementation is created here. Choosing a provider and actual session storage remains open, not implicitly approved by this spike.
- **Alternatives:** Managed identity reduces credential handling but needs account/budget/provider choice; self-hosted identity gives control but adds operations and RAM; custom password/JWT machinery is quick to demonstrate but creates unnecessary security ownership.
- **Why this fits:** Tests the selected Python ecosystem's protocol support without inventing authorization or exposing tenant data. The dashboard labels itself as a local shell.
- **Costs / failure modes:** No working login, callback verification, logout, session revocation or RBAC. State/PKCE primitives alone do not prove secure OIDC; issuer, audience, nonce, redirect allowlist and ID-token checks need a real provider integration.
- **Actual evidence:** See `test_auth_spike.py` and phase report; no identity-provider request, tokens or user accounts are created.
- **Revisit:** Before any user-specific endpoint or external deployment; developer selects issuer and session lifecycle.
- **Interview explanation:** “I separated an authentication compatibility experiment from a real login. A library can build a correct PKCE request, but that does not prove callback validation, revocation or tenant authorization. I left those as explicit gates rather than putting a fake user in the application.”
- **Follow-ups:** Where does tenant identity originate? A verified server session and membership lookup, still future work. Why no custom JWT? It adds key/token lifecycle risks without a requirement. Are loopback bindings sufficient for production? No; the entire deployment auth boundary remains unverified.
- **Related decisions:** ADR-016; DEC-133/134/203 and DEC-227.
