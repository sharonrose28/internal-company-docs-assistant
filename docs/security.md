# RBAC security model

PostgreSQL is the authorization source of truth. Administrators may access every document, managers may access and manage documents in their own department, and employees may read only documents present in `document_assignments`. Employee uploads create an assignment for the uploader; employees cannot delete documents or manage assignments.

## Retrieval enforcement

Qdrant authorization payloads are generated from PostgreSQL during indexing:

- Manager searches require an exact `department` match.
- Employee searches require the employee ID in `allowed_user_ids`.
- Administrator searches do not add an authorization restriction.

These conditions are included in both dense and sparse hybrid prefetches, so unauthorized vectors never enter the candidate set. Explicit document filters are authorized in PostgreSQL before query embedding or Qdrant access. Returned document IDs are checked against PostgreSQL again before chunks leave the retrieval service. This second check prevents leakage during the short interval between a PostgreSQL assignment revocation and its asynchronous Qdrant payload update.

Assignment changes enqueue a Celery payload synchronization task. Document deletion captures and deletes Qdrant points as well as the stored source file. Existing-but-unauthorized document and assignment operations return HTTP 403.

## Operational considerations

- Keep JWT access tokens short-lived and reject inactive users or stale token versions.
- Never accept roles, departments, or allowed-user IDs from the search request; derive them from the authenticated database user.
- Scope any response cache by user authorization fingerprint and invalidate it when assignments or roles change.
- Do not log document text, vector payloads, credentials, or unauthorized candidate data.
- Alert on repeated 403 responses, assignment changes, Qdrant synchronization failures, and permission post-check mismatches.
- Use private networking, TLS, encryption at rest, least-privilege service credentials, and append-only audit logging in production.
- Consider PostgreSQL row-level security as an additional layer, but not a replacement for application and vector-store enforcement.
