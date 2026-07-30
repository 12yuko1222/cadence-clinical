# Data Lifecycle Specification: eTMF Quality Control (QC) Review Lifecycle

## 1. Overview
The electronic Trial Master File (eTMF) Quality Control (QC) Review Lifecycle is a critical, multi-stage data review workflow implemented to guarantee data integrity, completeness, and regulatory compliance under FDA 21 CFR Part 11, GAMP 5, and EU Annex 11.

---

## 2. Document Status Values
Documents in the eTMF progress through the following status values:
- **DRAFT**: The initial, unverified state of a newly ingested or uploaded document.
- **TECHNICAL_QC**: The document is undergoing technical Quality Control checking (e.g., verifying readability, taxonomy mappings, file format compliance, and basic metadata accuracy).
- **CLINICAL_QC**: The document is undergoing clinical Quality Control review to confirm context validity, protocol alignment, and adherence to GCP/ICH standards.
- **APPROVED**: The document has successfully completed all QC phases and is officially approved as an active record in the eTMF.
- **ARCHIVED**: Active clinical records are securely archived once a study milestone or the entire trial reaches completion. This is a terminal state.
- **REJECTED**: A document that fails technical or clinical review is rejected, allowing authors to correct and resubmit it (transitioning back to DRAFT).

---

## 3. Allowed Transitions (Validated State Machine)
To prevent unauthorized state jumps or bypass of QC controls, transitions are strictly governed by a state machine validation gate:

```
[ DRAFT ] ──► [ TECHNICAL_QC ] ──► [ CLINICAL_QC ] ──► [ APPROVED ] ──► [ ARCHIVED ]
                   │                     │                    │
                   ▼                     ▼                    ▼
             [ REJECTED ]          [ REJECTED ]         [ REJECTED ]
                   │
                   ▼
               [ DRAFT ] (Re-submit)
```

- **DRAFT** can only transition to **TECHNICAL_QC**.
- **TECHNICAL_QC** can transition to **CLINICAL_QC** or **REJECTED**.
- **CLINICAL_QC** can transition to **APPROVED** or **REJECTED**.
- **APPROVED** can transition to **ARCHIVED** or **REJECTED**.
- **REJECTED** can transition to **DRAFT** (restarting the review lifecycle).
- **ARCHIVED** is a terminal state; no further transitions are permitted.

---

## 4. Role-Based Access Control (RBAC) Gates
Transitions can only be performed by users holding the designated roles:

| Target Status | Allowed Actor Roles | Description |
| :--- | :--- | :--- |
| **DRAFT** | `sponsor_dm`, `sponsor_clinical`, `admin` | Resubmitting a corrected document or reverting from rejected. |
| **TECHNICAL_QC** | `sponsor_dm`, `admin` | Technical QC review performed by Sponsor Data Managers. |
| **CLINICAL_QC** | `sponsor_clinical`, `admin`, `monitor` | Clinical QC review performed by Clinical Reviewers/Monitors. |
| **APPROVED** | `sponsor_dm`, `sponsor_clinical`, `admin` | Final validation of both technical and clinical verification steps. |
| **ARCHIVED** | `sponsor_dm`, `admin` | Relocating approved active documents to clinical archives. |
| **REJECTED** | `sponsor_dm`, `sponsor_clinical`, `admin` | Rejecting a document from any of the active QC/Approval stages. |

---

## 5. Audit Trail & 21 CFR Part 11 Compliance
Every transition executes under strict electronic signature and auditing controls:
1. **Append-Only History Logs (`DocumentQCTransition`)**: Every successful status transition is persisted in an immutable, append-only ledger tracking:
   - Document ID reference.
   - From status & To status.
   - Actor identity & Actor roles.
   - 21 CFR Part 11 change justification reason (mandatory, minimum 10 characters).
   - Timestamp.
2. **Immutable Audit Trail (`TMFAuditLog`)**: The system automatically registers a parallel record in the global eTMF audit log.

---

# Data Lifecycle Specification: Medical Coding Lifecycle

## 1. Overview
The Medical Coding Engine translates raw, unstructured clinical verbatim descriptions (e.g., adverse events, medical history, or concomitant medications) into standard codes from dictionaries like MedDRA and WHODrug. This workflow supports precise analysis, clinical safety reporting, and submission-ready database generation while enforcing strict regulatory auditing compliance under FDA 21 CFR Part 11.

---

## 2. Ingest → Match → Assignment → Query → Recoding Flow

```
[ raw verbatim ingest ] ────► [ fuzzy matching & scoring ]
                                     │
      ┌──────────────────────────────┼──────────────────────────────┐
      ▼ (Score >= 0.85)              ▼ (Score 0.60 to 0.84)         ▼ (Score < 0.60)
[ AUTO_CODED ]               [ SUGGESTED ]                  [ QUERY_PENDING ]
      │                              │                              │
      │ (auto-promoted)              ▼ (Manual review loop)         ▼ (Triggers EDC Query)
      │                      [ ACCEPT ] or [ OVERRIDE ] ──► [ SYSTEM_CODING query ]
      │                              │                              │
      ▼                              ▼                              ▼ (Resolved by re-verbatim)
[ Active Assignment ] ◄──────────────┴──────────────────────────────┘
      │
      ▼ (Up-versioning dictionary impact)
[ ClinicalCodingLedger ] (Audit historical trail & status transitions)
```

### Stage 1: Ingest (Dictionary Loading)
- **Action**: Standard dictionaries are imported dynamically via the authenticated Gateway.
- **Accountable Roles**: `TERMINOLOGY_MANAGER` and `SYSTEM_ADMIN` hold exclusive privileges.
- **Process**: Parsing handles ASCII files inside `.zip` archives containing either MedDRA format files or WHODrug format files.
- **Auditing**: Records an immutable `DictionaryImportJob` tracking the job state, percentage completion, row counts, errors, and standard audit log entries for full lifecycle traceability.

### Stage 2: Match (Fuzzy Similarity Matching)
- **Process**: Raw text ingested into the system is normalized via:
  - Case folding.
  - Suffix-stripping stemming rules (e.g., stripping `s`, `es`, `ing`, `ed`, `ly`, etc.).
  - Clinical stop-phrase/word removal (e.g., removing words like `acute`, `mild`, `severe`, `history of`, etc.).
- **Scoring**: A hybrid deterministic scorer calculates token alignment:
  $$\text{Score} = 0.4 \times S_{\text{Levenshtein}} + 0.6 \times S_{\text{Cosine}}$$
- **Confidence Gates**:
  1. **AUTO-CODED (Score $\ge$ 0.85)**: High-confidence exact/near-exact matches are linked to standard codes immediately.
  2. **SUGGESTIONS (Score 0.60 to 0.84)**: Up to three ranked code suggestions are stored on the assignment. Status changes to `SUGGESTED`.
  3. **UNCODABLE (Score $<$ 0.60)**: Verbatim strings with low matcher confidence are placed into `QUERY_PENDING`.

### Stage 3: Assignment / Review (Manual Coder Loop)
- **Process**: Data Managers and Coders review and resolve `SUGGESTED` or `QUERY_PENDING` records.
- **Allowed Actions**:
  - **ACCEPT**: Commits suggestion index as final coding meaning.
  - **OVERRIDE**: Manually overrides the code with a verified dictionary concept.
- **Auditing / Part 11**: Coder actions require standard Gateway Signature Version 2 authentication headers, validating credentials and carrying an explicit, non-empty GxP `reason_for_change` justification. Each manual decision is recorded permanently in `ClinicalCodingLedger`.

### Stage 4: Query (Uncodable Query Generation)
- **Process**: For any `UNCODABLE` assignment, the system automatically triggers an open, actionable `ClinicalQuery` with origin `SYSTEM_CODING` and action required `RE-ENTER_VERBATIM`.
- **Identity & PII Isolation**: Query logs specify the exact table, field, and observation coordinates, but omit clinical subject IDs and demographics to maintain blinding and isolate PII data.
- **Resolution Transitions**:
  - Resolving or cancelling the `SYSTEM_CODING` query reverts the assignment status back to `UNCODED`, placing it back into the manual review loop.
  - Conversely, a manual coder action (`ACCEPT` or `OVERRIDE`) on the pending assignment automatically transitions the query status to `CLOSED` and attaches resolution notes.

### Stage 5: Recoding & Up-Versioning Ledger
- **Process**: When a new dictionary version is imported, an impact analysis compares existing coded records.
- **Outcomes**:
  - **Unchanged**: Automatic promotion to the new version.
  - **Reclassified**: Status changed to `RECODING_REQUIRED` with recoding status `PENDING`. Target is flagged for review.
  - **Deprecated**: Assigned code is no longer present; status changes to `RECODING_REQUIRED` and recoding status `PENDING` to trigger manual recoding.
- **Auditing**: Pre-upversioning historical meanings are preserved intact under the original version indices, and transitions are written idempotently to the `ClinicalCodingLedger` to maintain compliance.

---

## 3. Accountable Roles & Access Control Matrix

| Workflow Transition | Required Roles / Privileges | GxP / Part 11 Constraints |
| :--- | :--- | :--- |
| **Dictionary Ingestion** | `TERMINOLOGY_MANAGER`, `SYSTEM_ADMIN` | Synchronous layout verification & transaction rollback on failure. |
| **Fuzzy Matching** | System | Automated, deterministic logic. |
| **Accept Suggestions** | `sponsor_dm` (Data Manager), Coder synonyms | Requires gateway signature validation. |
| **Manual Override** | `sponsor_dm` (Data Manager), Coder synonyms | Requires signature validation + non-empty `reason_for_change`. |
| **Query Closure** | Coder Action or System Event | Automatically synced on manual coder decision. |
| **Impact Analysis** | `TERMINOLOGY_MANAGER`, `SYSTEM_ADMIN` | Idempotent ledger updates. |

---

## 4. Operational & Cache Configuration
- **Cache TTL**: The thread-safe medical coding lookup cache uses a configurable expiration parameter via the `CODING_CACHE_TTL` environment variable (default: `10.0` seconds).
- **Graceful Cache Fallback**: In the event of backend database errors or connectivity failures, the system automatically falls back to serving stale/expired cached results to prevent user interface degradation.
- **Supported Dictionary Formats**:
  - **MedDRA**: Stream parses standard ASCII files including `llt.asc`, `pt.asc`, `hlt.asc`, `hlgt.asc`, `soc.asc`, and `mdhier.asc`.
  - **WHODrug**: Fixed-width format files (e.g., standard B3 DD.txt, ING.txt, ATC.txt, DADA.txt, DI.txt) or delimited (CSV, PSV) text formats using custom mappings and header configurations.
- **Licensed Content Note**: In-repo storage of licensed MedDRA or WHODrug terminology distributions is strictly forbidden. All testing environments must run using small, synthetic, in-memory fixtures.

---

# Data Lifecycle Specification: eTMF Document Redaction Lifecycle

## 1. Overview
The eTMF Document Redaction Lifecycle defines the security boundaries, operational flows, and regulatory data-handling logic for removing Personally Identifiable Information (PII) and Protected Health Information (PHI) from clinical documents before external distribution, auditor review, or public disclosure. This lifecycle fulfills the traceability and verification requirements of **PRD-TMF-005** and **Trace-12**.

---

## 2. Redaction Architecture & System Boundaries

```mermaid
graph TD
    A[Raw Unredacted Document] -->|Retained for GxP Trace Auditing| B[(Secure eTMF Storage)]
    A -->|POST /auto-redact or /manual-redact| C[De-identification Engine]
    C -->|Regex Scanners & Literal Terms| D[PII/PHI Detection & Overlap Resolution]
    D -->|Apply Transforms| E[Redacted Successor Version]
    D -->|Build Manifest| F[Redaction Manifest]
    F -->|HMAC-SHA256 Signature| G[Signed Cryptographic Manifest]
    E -->|Linked back to Source| H[(Secure eTMF Storage)]
    G --> I[TMFAuditLog REDACT Entry]

    style A fill:#fdd,stroke:#f66,stroke-width:2px
    style E fill:#dfd,stroke:#6b6,stroke-width:2px
    style B fill:#eef,stroke:#99b,stroke-width:2px
    style H fill:#eef,stroke:#99b,stroke-width:2px
```

The redaction engine is split into two layers:
1. **Shared Detection Layer (`packages/deid`)**: A pure-Python detection and sanitization package implementing regex-based scans, literal word scans, overlap resolution, transformation strategy application, and cryptographic signature generation.
2. **Service Gateway Layer (`apps/etmf`)**: Exposes `/api/v1/etmf/documents/{document_id}/auto-redact` and `/manual-redact` endpoints. It resolves versions, validates and logs Part 11 justifications, writes non-sensitive audit events, and restricts access to raw unredacted original files.

---

## 3. Compliance Profiles & Regulatory Disclosure Contexts

The de-identification engine implements three discrete, standardized compliance profiles that govern active PII/PHI categories and operational intents:

### HIPAA (US Health Insurance Portability and Accountability Act)
- **Operational Intent**: Satisfies the US "Safe Harbor" de-identification standard for sanitizing documents to be shared with sponsors, research partners, or US regulatory agencies (FDA).
- **Active Categories**: Direct and indirect identifiers (Emails, Phone/Fax Numbers, Social Security / National IDs, IP/MAC Addresses, URLs, ZIP/Geographic codes, Dates, Medical Record/Account Numbers, Age above 89, and custom terms).

### GDPR (EU General Data Protection Regulation)
- **Operational Intent**: Satisfies strict personal data handling rules for clinical subjects and trial coordinators residing in the EU. Focuses on removing direct and indirect identifiers that could lead to identity reconstruction.
- **Active Categories**: Direct and indirect identifiers (Emails, Phone/Fax Numbers, Social Security / National IDs, IP/MAC Addresses, URLs, ZIP/Geographic codes, Dates, Medical Record/Account Numbers, Age above 89, and custom terms).

### EU CTR (European Union Clinical Trials Regulation)
- **Operational Intent**: Focuses on the public-disclosure framing mandated by the EU Clinical Trials Registry (under Regulation EU No 536/2014). Ensures clinical study documents can be published transparently to the public database without revealing any patient identities, while maintaining geographic granularity (ZIP codes and IP addresses) which are relevant to clinical execution and are thus preserved.
- **Active Categories**: Focuses strictly on patient anonymity and direct clinical trial patient identifiers (Emails, Phone/Fax Numbers, Social Security / National IDs, Dates, Medical Record/Account Numbers, Age above 89, and custom terms).

---

## 4. De-identification Transforms & Default Date-Shifting

The engine applies distinct, GxP-compliant transform strategies to the detected matches:
1. **Masking (`mask`)**: Replaces the sensitive value with a standard placeholder (e.g., `[EMAIL]`, `[SSN_NATIONAL_ID]`).
2. **Deterministic Pseudonymization (`pseudonymize`)**: Generates a cryptographically strong, non-reversible, deterministic hash of the verbatim value using HMAC-SHA256 and the workspace `REDACTION_SIGNING_SECRET` / `"internal-gateway-secret-12345"`.
3. **Age Capping (`age_cap`)**: Generalizes age values that exceed a set limit. Standard policy generalizes any age above 89 to `89+`.
4. **Configurable Date-Shifting (`date_shift`)**:
   - **Default Date-Shift Policy**: By default, dates are shifted forward by exactly **365 days** (1 year) to preserve longitudinal intervals (e.g., matching subsequent visits, adverse event spans, or dosing times) while destroying original calendar values.
   - **Configurability**: The date shifting offset is fully configurable via the `shift_days` parameter on the transform execution to handle study-specific anonymization schedules.

---

## 5. Document Version Preservation & Access Boundaries

To satisfy 21 CFR Part 11 electronic records tracing and GxP compliance:
- **Non-Destructive Version Preservation**: Original, unredacted documents are never overwritten. A redaction event increments the document's `version_index` and creates a redacted successor document version linked back to the source version using the `redaction_source_id` reference column.
- **Auditor & Inspector Lock state**: Read-only roles (`auditor`, `inspector`, `regulatory_inspector`) are strictly blocked from accessing the raw, unredacted source documents (returning HTTP 403 Forbidden) once a redacted successor exists. Only write-privileged roles (e.g., Sponsor DM) can view raw originals.
- **Trial Lock Safeguards**: If the clinical study or trial is locked, any subsequent ingestion, manual/automated redaction, or transition attempts are blocked, returning HTTP 403 `IMMUTABILITY_VIOLATION`.

---

## 6. Manifest Signing, Audit Trails & Sensitive Data Restrictions

Every redaction operation creates a highly detailed, immutable cryptographic paper trail:
1. **Signed Redaction Manifest**:
   - A structured Pydantic-based `RedactionManifest` records redaction counts per category, operator identity, change reason justification, source version, target version, and character span metadata.
   - It is signed symmetrically using HMAC-SHA256 with the secret `REDACTION_SIGNING_SECRET`.
   - The signed manifest data is saved permanently inside the redacted document's `redaction_manifest_json` column.
2. **Sensitive-Data Restrictions (PII/PHI Exclusion)**:
   - To maintain blinding and comply with GDPR/HIPAA standards, **raw matched PII/PHI values are strictly excluded from all audit trails, logging records, and manifest files**. Only the category, strategy, and replacement values are preserved.
3. **Immutable Audit Trail Logging**:
   - The system logs a non-sensitive `REDACT` action to the immutable database-backed `TMFAuditLog`, containing the actor ID, roles, source/redacted version indices, and the cryptographic manifest signature to ensure tamper-evident non-repudiation.

---

# Data Lifecycle Specification: Global Library & Clinical Study Instances

## 1. Overview
The Global Library in the Metadata Designer (MDR/SDR) service (`apps/designer`) serves as the central, multi-tenant repository for reusable clinical protocol definitions. This specification defines the data lifecycle, retention rules, and strict tenant partitioning that separate shared global reference templates from trial-specific (study instance) execution data. It ensures system compliance under FDA 21 CFR Part 11, GxP standards, and GDPR multi-tenant guidelines, satisfying **Trace-3**.

---

## 2. Shared Library Objects versus Study-Instance Data

The platform enforces a clear distinction between master template objects and localized trial instances:

```
[ Global Library (Master Data) ] ──────► [ POST /library-instances ] ──────► [ Study Instance (Execution) ]
 - Owned by Sponsor A                     - Copy-on-Instantiation            - Scope bound to Study
 - Versioned via Graph Chains             - Captures source link             - Local Overrides Allowed
 - Locked statuses are Immutable          - Retains pedigree trace           - Lifespan bound to Trial
```

### Global Library Templates (Master Reference Data)
- **Nature**: High-quality, reusable blueprint templates representing clinical design standards (`FORM`, `DATA_ELEMENT`, `ARM`, `VISIT`).
- **Storage**: Persisted as graph nodes inside Neo4j.
- **Auditing & Change Trails**: Modifications create new versioned nodes. Prior states are retained intact and chained linearly using `[:PREVIOUS_VERSION]` relationships to preserve historical protocol reproducibility.

### Study Library Instances (Trial-Specific Data)
- **Nature**: Active, study-scoped configurations instantiated for a particular clinical protocol.
- **Storage**: Persisted as separate `:LibraryObjectInstance` nodes linked to the study root `:Study`.
- **Overrides**: Study teams can customize or override these instantiated templates.
- **Source Linkage**: Upon instantiation, the platform records a strict `[:INSTANTIATED_FROM]` relationship mapping the instance back to the exact source library template version (tracking source ID, version index, and sponsor ID). This guarantees absolute provenance and clinical traceability.
- **Isolation of Modifying Effects**: Local overrides exist purely at the study-instance level. Modifying an instantiated copy has absolutely zero impact on the master Global Library template, preserving the template's purity.

---

## 3. Logical Tenant Partitioning & Sponsor Separation Guidelines

To enforce strict clinical trial separation and prevent cross-sponsor metadata leakage:
1. **Cryptographic Context Verification**: The API Gateway decodes the caller's Keycloak JWT, validates roles, and injects signed headers (`X-Sponsor-Id`, `X-Tenant-Id`) downstream.
2. **Whitespace Gating**: The Metadata Designer service strictly parses incoming sponsor attributes. Write, read, list, or transition attempts are instantly rejected with HTTP 403 Forbidden if the sponsor ID is:
   - Absent or missing.
   - Null or empty (`""`).
   - Whitespace-only (e.g., `"   "`).
3. **Sponsor Boundary Enforcement**: Database queries are strictly scoped. Every query automatically appends a sponsor isolation parameter (e.g. `n.sponsor_id = $sponsor_id`). Callers are completely blocked from reading, listing, updating, or instantiating templates belonging to other sponsors (returning HTTP 404 or 403).

---

## 4. Retention Policy & Lifespan Rules

The operational lifespan of library data and study data is governed by distinct regulatory retention schedules:

| Data Classification | Lifecycle States | Retention Trigger | Compliance Retention Timeline |
| :--- | :--- | :--- | :--- |
| **Global Library Templates** | `DRAFT`, `IN_REVIEW`, `APPROVED`, `PUBLISHED`, `ARCHIVED` | Transition to `ARCHIVED` | Permanently retained as master metadata. Retained for 25 years post-trial completion per clinical master file guidelines. |
| **Study Library Instances** | Active Trial State | Trial Completion or Soft Deletion | Linked directly to the study lifecycle. Retained/archived in parallel with study trial master records. |

### Immutability of Locked Template Statuses
- Once a template version's status is transitioned to `PUBLISHED` or `ARCHIVED`, its payload is locked. Standard `PUT` mutations on these records are strictly blocked at the API layer, raising an `IMMUTABILITY_VIOLATION` (HTTP 403 Forbidden).
- **Formal Amendments**: To evolve a locked or in-use template, users must call `/api/v1/mdr/library/{id}/amend`. This copies the template's payload into a new, separate draft version node (incrementing the version sequence) while keeping existing active studies linked to the original version.

### Non-Destructive Soft-Deletion Guidelines
- Deletions are strictly non-destructive. To prevent historical audit trail breaks, master templates and study instances are never deleted from the database. Instead:
  - Deletions write a new version marked as `is_deleted = true`.
  - The previous active state remains securely preserved in the graph version chain, enabling complete retrospective reconstructibility of any trial configuration at any historical timestamp.

---

# Data Lifecycle Specification: Protocol Amendment Lifecycle

## 1. Overview
The Protocol Amendment and Clinical Data Lifecycle governs mid-study protocol modifications, version propagation, historical immutability, and patient safety re-consent gating. To safeguard clinical study integrity under FDA 21 CFR Part 11, GAMP 5, and EU Annex 11, the system guarantees that historical records are never overwritten (zero data loss) and that active clinical transitions require explicit, documented patient consent corresponding to the approved protocol version tag. This section traces back to the requirements of **PRD-SYS-001**, **PRD-MDR-002**, **PRD-SUB-007**, **TDD §3.4/§3.5**, and **QA §5.1 TC-VAL-LOG-001**.

---

## 2. Protocol Version Statuses
Protocol versions progress through a validated state machine, representing controlled stages of clinical approval:

- **DRAFT**: The initial, mutable state of a new or amended study protocol. All graph elements (arms, epochs, visits, forms, blocks) can be updated or deleted.
- **ACTIVE**: The protocol version is deployed but not yet finalized or released to clinical production.
- **LOCKED**: The version is frozen and undergoes final signature validation checks. All modifications are strictly blocked.
- **PUBLISHED**: The version is formally released to clinical execution sites. This is a GxP-validated master metadata record.
- **ARCHIVED**: Superseded or retired versions are archived for regulatory audit history. They remain permanently readable.
- **FROZEN**: A transient state indicating a version has been finalized and cannot be modified under any standard workflow.

### Mutable vs. Immutable Lifecycle States
- **Mutable States**: `DRAFT` and `ACTIVE`. Graph elements can be added, updated, or soft-deleted.
- **Immutable/Frozen States**: `LOCKED`, `PUBLISHED`, `ARCHIVED`, and `FROZEN`. Standard PUT/POST/DELETE operations instantly raise an immutability violation error.

---

## 3. Amendment Branching and Version Succession Flow
When a study designer initiates an amendment on a finalized protocol version, the system creates a transaction-safe branch (cloned subgraph) without altering the source version:

```mermaid
graph TD
    Parent[Parent Version: LOCKED/PUBLISHED] -->|POST /api/designer/protocols/{id}/amend| Amend[Amend Engine]
    Amend -->|Deep-Copy Subgraph| Successor[New Version: DRAFT]
    Successor -->|PREVIOUS_VERSION Link| Parent
    Successor -->|version_index increment| IncIndex[version_index = parent + 1]
    Successor -->|version_tag bump| BumpTag[Tag: v1.0 -> v1.1 or v2.0]
```

- **Branching Action**: A formal amendment fork executes deep copies of up to 4 levels of structural relations (HAS_ARM, HAS_EPOCH, HAS_VISIT, HAS_FORM, HAS_ACTIVITY).
- **History Linkage**: The new DRAFT successor is connected back to its immediate parent node via a `[:PREVIOUS_VERSION]` relationship, preserving an unbroken pedigree chain for full retrospective protocol reconstruction.

---

## 4. Designer Service Mechanics and Immutability Guards
The Metadata Designer service (`apps/designer`) enforces GxP metadata integrity through structural and API-level constraints:

### API Endpoints and Contract Shapes for Versioning
The following endpoints orchestrate the metadata versioning lifecycle:
- **Version Creation**: `POST /api/v1/studies/{study_id}/versions` initiates a new study version. It receives a `CreateStudyVersionRequest` payload containing properties `id`, `version_tag`, `status`, and `version_index`, returning a standard status confirmation.
- **Protocol Amendment**: `POST /api/designer/protocols/{id}/amend` deep-copies the entire parent protocol configuration. It receives a `ProtocolAmendRequest` payload containing fields `amendment_type` (defaulting to `"minor"`) or `type`, returning a structured response containing `{new_version, status, parent_version}` to verify successor generation.
- **Form-Level Graph Diff**: `GET /api/v1/studies/{study_id}/versions/diff` compares two subgraphs, returning `added_nodes`, `modified_nodes`, and `deleted_nodes` based on key and XML comparisons.
- **Field-Level Diff**: `GET /api/v1/studies/{study_id}/differences` executes a 1D in-memory flat difference mapping of flattened dot-notated paths.

### Immutability Guards and Branching semantics
- **Assertion Handlers**: `assert_study_version_mutable` and `assert_graph_mutable` run on every mutation, raising a `403 Forbidden` exception if the target's status resides in `APPROVED`, `SIGNED`, `LOCKED`, `PUBLISHED`, or `ARCHIVED`.
- **Version Bumping Rules**: Bumping a version (`bump_version`) performs a major bump (e.g. `1.0` $\rightarrow$ `2.0`) for `"major"` or `"restructuring"` types, and a minor bump (e.g. `1.0` $\rightarrow$ `1.1`) otherwise. The `version_index` always increments by exactly `1` (verified in `tests/test_study_versions.py`).
- **Cryptographic Version Integrity**: To prevent out-of-band tampering, study version attributes are checked using a canonical HMAC-SHA256 signature generated and verified symmetrically (`generate_canonical_signature`/`verify_version_signature` in `packages/security/signing.py`). This is strictly used for cryptographic integrity verification of study payloads before loading, and is independent of user electronic signatures.
- **Non-Destructive/Immutable-History Guarantee**: To preserve clinical audit trails, study metadata configurations are never physically deleted. Soft deletions write a new version marked as `is_deleted = true`, keeping historical structures intact.

---

## 5. Error & Concurrency Contracts
The Metadata Designer and Execution services implement a unified exception-to-HTTP mapping to ensure standard GxP error representation:

| Internal Python Exception | HTTP Code | Error Code / Details | Description |
| :--- | :--- | :--- | :--- |
| `ImmutabilityViolationError` | `403` | `IMMUTABILITY_VIOLATION` | Raised when attempting to mutate a locked, published, or archived graph or version. |
| `ConcurrentLockingError` | `409` | `CONCURRENT_LOCKING_CONFLICT` | Raised during parallel creation of identical version indexes or tags. |
| `InvalidSignatureError` | `400` | `INVALID_OR_MISSING_SIGNATURE` | Raised when a study version's cryptographic canonical signature fails verification. |
| `LibraryObjectInUseError` | `409` | `LIBRARY_OBJECT_IN_USE` | Raised when modifying a Global Library template currently in use by an active study. |

### Concurrency-Safety Model
1. **Neo4j Study Root Locking**: The Designer service executes an exclusive write-lock (`SET s._lock = true`) on the Study root node during amendments and version promotions to serialize graph updates.
2. **Sequential Version Indices Guard**: Databases enforce unique composite indexes on `(study_id, version_index)` and `(study_id, version_tag)` to prevent race conditions from creating parallel timelines.
3. **Mock/In-Memory Fallback Path**: For non-Neo4j testing environments, a thread-safe dictionary-based locking scheme (`_amendment_locks`) handles isolation in memory.

---

## 6. Accountable Roles & Access Control Matrix

| Action / Transition | Allowed Actor Roles | GxP / Part 11 Constraints |
| :--- | :--- | :--- |
| **Initiate Study version** | `sponsor_designer`, `sponsor_dm`, `admin` | Requires explicit `X-Change-Reason` header. |
| **Amend Study version** | `sponsor_designer`, `sponsor_dm`, `admin` | Spawns a transaction-safe draft copy; parent remains immutable. |
| **Lock / Publish version** | `sponsor_designer`, `sponsor_dm`, `sponsor_admin`, `admin` | Performs cryptographic canonical signature generation. |
| **Execute PI Sign-Off** | `Site Principal Investigator (PI)`, synonyms | Enforces re-authentication step-up token and records GxP signature. |
| **Record Re-Consent** | `Site Investigator`, `CRC`, `admin` | Instantly unblocks execution gating on clinical data tables. |

---

## 7. Audit Trail & 21 CFR Part 11 Compliance
Every state change, protocol version transition, and clinical transaction generates an append-only, immutable paper trail that complies with GxP 21 CFR Part 11 standards:

1. **Mandated Audit Fields (`PRD-SYS-001`)**: Every table representing metadata or transaction states inherits and enforces the presence of exactly four core audit fields:
   - `created_at`: High-precision UTC timestamp generated by the server upon commit.
   - `created_by`: Deterministic OIDC user identity string (`sub`) of the authenticated user performing the write.
   - `reason_for_change`: A mandatory string of minimum 10 characters and maximum 1000 characters capturing the clinical/business justification.
   - `version_index`: An integer representing the version sequence of the record, beginning at `1` and auto-incrementing by `1` with every update.
2. **Append-Only History Records**: Mutations do not overwrite existing transaction blocks. Changes to protocol configurations write new Action records (`Action` / `change_reason`) to the immutable history log while soft-deletes write a deleted state, maintaining full reconstructibility of any trial configuration at any historical timestamp.

---

## 8. Execution Service Re-Consent Gating
Clinical Trial Execution (`apps/execution`) enforces exact-version re-consent gating to protect patient safety.

### SubjectConsent Data Model
The `SubjectConsent` table stores subject-specific consent statuses:
- `study_id`: Alphanumeric study identifier.
- `version_tag`: Alphanumeric protocol version tag (e.g., `"2.0"`).
- `version_index`: Positive integer chronological version index.
- `icf_signed`: Boolean indicating if the Informed Consent Form is signed.
- `icf_signed_date`: UTC timestamp of the signature.
- `requires_reconsent`: Boolean indicating if this version requires subjects to sign a new consent before entering more data.

### The Session before_flush Gating Mechanics
- **The Database Gate**: Inside `apps/execution/database/audit.py`, a `before_flush` event listener intercepts modifications to clinical tables (`clinical_subjects`, `clinical_visits`, `clinical_observations`, `form_submissions`).
- **Gating Evaluation**: The database gate checks if any higher-index protocol version is flagged as `requires_reconsent = true`. If a subject has not signed a matching `SubjectConsent` record for that newer version, the gate instantly aborts the database transaction and raises:
  `PermissionError("Re-Consent Required - Demographics & Visit Forms Locked")`
- **Clearing Semantics**: Recording a new `SubjectConsent` with `icf_signed = true` corresponding to the latest version immediately clears the blocking flag, allowing clinical workflow writes to proceed (validated by `tests/test_reconsent_blocking.py` under `PRD-SUB-007`).
- **Upstream Separation**: The `apps/econsent` module functions strictly as an independent upstream translation and translation-caching service, and does not participate in execution-level transaction blocking or amendment gating.

---

## 9. Planned / Pending Implementation

### Feature #321: Protocol Version Stamping & Non-Destructive Reconciliation (Future Scope)
* **Protocol Version Stamping**: Future releases will introduce mandatory protocol version-stamping on clinical transaction entities. Every newly created `ClinicalObservation` and `FormSubmission` will store the active `protocol_version_tag` and `protocol_version_index` at the moment of entry.
* **Non-Destructive Reconciliation**: When migrating existing subject records to an amended protocol version, the system will apply non-destructive migration rules. For fields that are renamed or removed, the original historical observation entries will remain untouched. The system will write a successor observation mapping the new target coordinates, tracking provenance through a migration source ID reference to ensure no data loss occurs.

### Feature #331: eTMF Linkage and version History (Future Scope)
* **eTMF Linkage**: Future releases will connect eTMF documents directly to the protocol versions they govern. The `TMFDocument` model will establish a foreign key or graph relationship mapping to the canonical `ProtocolVersionRef`.
* **ExpectedDocument Alignment**: Seeding expected document templates (`ExpectedDocument`) will dynamically adapt according to the active protocol version. When a protocol version transitions, the expected document list will automatically register new required documents (e.g. adding a new Consent Form requirement for v2.0), while archiving outdated requirements in accordance with the GxP data preservation policy.

---

# Data Lifecycle Specification: Native 21 CFR Part 11 eSignature Lifecycle

## 1. Overview
The Native 21 CFR Part 11 eSignature Lifecycle governs the progression of clinical and regulatory artifacts from unsigned drafts to fully signed, cryptographically secured, and immutable historical records. This workflow ensures non-repudiation, signer re-authentication, and strict state locking across all core microservices, satisfying **PRD-SYS-001** and **PRD-TMF-005**.

---

## 2. Unsigned-to-Signed Transition Lifecycle

```
[ Artifact Ingestion ]
         │
         ▼
[ PENDING / UNSIGNED ] ──( Re-Authenticate & Apply Sign-off )──► [ SIGNED / APPROVED ]
   - status: active QC states                                       - status: "SIGNED"
   - approval_status: "PENDING"                                     - approval_status: "APPROVED"
   - signature_manifestation: null                                  - signature_manifestation: [Certificate-bound Block]
   - Mutations Allowed (QC transitions, redaction)                  - Mutations Blocked (IMMUTABILITY_VIOLATION)
```

1. **Active/Unsigned Phase**: Newly ingested artifacts (e.g. eTMF documents, protocol versions) begin with `approval_status = "PENDING"`. In this state, they can undergo active QC review transitions, automated/manual redactions, or minor updates.
2. **Re-Authentication Trigger**: Applying an electronic signature requires immediate "double-keying" re-authentication of the signer's credentials, regardless of an active session.
3. **Locked/Signed Phase**: Upon successful re-authentication and signature execution, the artifact's `status` transitions to `SIGNED` and its `approval_status` transitions to `APPROVED`. The record becomes completely locked, preventing all future edits.

---

## 3. Dual-Layer Security: Gateway Authorization vs. Downstream Manifestation

To secure electronic records without propagating raw credentials across service boundaries, the architecture enforces a strict dual-layer authorization-manifestation design:

### Layer 1: Gateway Signature Token Authorization (Short-Lived Intent)
- **Path**: `apps/gateway/main.py` ➔ `packages/security/middleware.py`
- **Mechanism**: The user re-enters their password (and optional TOTP) into the reusable Vue 3 component `apps/web/src/components/SignatureCaptureModal.vue`. The API Gateway validates these credentials against Keycloak and issues a short-lived **Signature Token (`X-Sig-Token`)** signed via HS256 with `GATEWAY_SECRET`.
- **Properties**:
  - **Temporal Limitation**: Hard expired in **60 seconds** (`exp = iat + 60.0`).
  - **Single-Use Replay Prevention**: Contains a unique UUID `jti` verified against an in-memory/distributed cache to block replay attacks.
  - **Action & Identity Binding**: Explicitly bound to the executing user (`sub` claim) and the exact REST endpoint route (`action` claim).

### Layer 2: Certificate-Bound Record Manifestation (Persistent Non-Repudiation)
- **Path**: `apps/etmf/main.py` or `apps/designer/main.py`
- **Mechanism**: Upon verifying the `X-Sig-Token`, the downstream service generates a transient RSA private key and self-signed X.509 certificate on-the-fly.
- **Persistent Signature Block**: The service signs the canonical representation of the record (including its SHA-256 content hash, signer OIDC ID, UTC timestamp, and controlled signing reason).
- **Result**: A structured, mathematically verifiable `SignatureManifestation` (containing the signature, certificate PEM, and key identifier) is persisted permanently in the record's database columns (`signature_manifestation` / `signature_manifestation_json`). This fulfills the Part 11 requirements for the printed name of the signer, UTC timestamp, and the meaning of the signature (§ 11.50).

---

## 4. Trust Boundaries & Token/Error Contracts

The interaction across the UI, Gateway, and Downstream microservices is governed by clear error and token contracts:

| Event Scenario | HTTP Code | Error Code / Contract | Actionable UI Mitigation |
| :--- | :--- | :--- | :--- |
| **Missing/Expired Token** | `401 Unauthorized` | `REAUTHENTICATION_REQUIRED` or `JWTExpired` | Forces user to re-verify credentials in the modal and requests a fresh `X-Sig-Token`. |
| **User/Action Mismatch** | `401 Unauthorized` | `Mismatched signature token user` / `Action mismatch` | Rejects the signature execution, preventing token hijacking or cross-endpoint routing. |
| **Insufficient RBAC Roles** | `403 Forbidden` | `ROLE_INSUFFICIENT` / Permission check failure | Modal displays an error stating the user is not authorized to sign. |
| **Post-Signature Edit Attempt** | `403 Forbidden` | `IMMUTABILITY_VIOLATION` | Returns a blocked status response, writes a `MUTATION_REJECTED` audit event, and denies the update. |

---

## 5. Architectural Map of Components

The Part 11 eSignature workflow is fully realized and integrated across the following source paths:

- **Identity & Step-up Gateway Authentication**:
  - `apps/gateway/main.py` (Verify password and issue `X-Sig-Token`)
  - `packages/security/middleware.py` (Intercept and validate token claims)
  - `docs/SDLC/Signature_Token_Cryptographic_Contract.md` (Formal JWT specification)
- **Reusable Frontend Modal**:
  - `apps/web/src/components/SignatureCaptureModal.vue` (Credential capture, auto-clear, and error mapping)
- **eTMF Service Execution**:
  - `apps/etmf/main.py` (Sign-off endpoint: `POST /api/v1/etmf/documents/{document_id}/sign-off`)
  - `apps/etmf/models.py` (Persistence schema: `TMFDocument.signature_manifestation`)
  - `tests/test_etmf_signing_lifecycle.py` (E2E signing lifecycle and Merkle seal verification)
- **Metadata Designer Execution**:
  - `apps/designer/main.py` (Protocol approval endpoint: `POST /api/v1/studies/{study_id}/versions/{version_id}/approve`)
  - `apps/designer/delta.py` (Approve study delta and lock protocol graph nodes)

---

# Data Lifecycle Specification: SDTM/ADaM Export Privacy & De-identification

## 1. Overview
Structured biostatistical exports (CDISC SDTM and ADaM formats) must undergo an automated privacy and de-identification pass before external distribution or regulatory submission. This workflow ensures deterministic pseudonymization of subject identifiers, stable per-subject date-shifting, and age capping under the authoritative policy [ADR-108](./adr/2026-08-26-sdtm-adam-export-privacy.md).

## 2. Privacy Transformation Mechanics
The de-identification transform operates on assembled datasets immediately before serialization into CDISC Dataset-JSON format:
1. **Deterministic Pseudonymization**: Subject identifiers (`USUBJID`, `SUBJID`) and site identifiers (`SITEID`) are hashed deterministically using HMAC-SHA256 and the secure `BIOSTAT_EXPORT_SALT` token. This guarantees referential integrity across separate datasets, domains, and exports.
2. **Stable Per-Subject Date Shifting**: A stable numeric offset in the range `[-365, 365]` days is derived deterministically from the subject's original `USUBJID` before pseudonymization. All dates associated with that subject are shifted by this exact offset:
   - **SDTM string dates** (e.g. `AESTDTC`, `RFSTDTC` etc.) are shifted preserving partial dates and null-flavor placeholders.
   - **ADaM numeric dates** (e.g. `TRTSDT`, `ASTDT` etc.) are shifted by adding the offset directly to the SAS day integer value.
3. **Age Generalization**: Any subject age value exceeding 89 is capped at `89`.
