"""Allowed values for enum-like columns (SPEC §5). Stored as strings."""

from enum import StrEnum


class Locale(StrEnum):
    SW = "sw"
    EN = "en"


class OpportunityType(StrEnum):
    JOB = "job"
    INTERNSHIP = "internship"
    SCHOLARSHIP = "scholarship"
    FELLOWSHIP = "fellowship"
    HACKATHON = "hackathon"
    GRANT = "grant"
    CONFERENCE = "conference"
    COMPETITION = "competition"
    TRAINING = "training"


class EducationLevel(StrEnum):
    SECONDARY = "secondary"
    CERTIFICATE = "certificate"
    DIPLOMA = "diploma"
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"
    ANY = "any"


class OpenToTanzanians(StrEnum):
    YES = "yes"
    NO = "no"
    UNCLEAR = "unclear"


class Funding(StrEnum):
    FULLY_FUNDED = "fully_funded"
    PARTIALLY_FUNDED = "partially_funded"
    PAID = "paid"
    UNPAID = "unpaid"
    STIPEND = "stipend"
    UNCLEAR = "unclear"


class WorkMode(StrEnum):
    ONSITE = "onsite"
    REMOTE = "remote"
    HYBRID = "hybrid"
    UNCLEAR = "unclear"


class DeadlineType(StrEnum):
    FIXED = "fixed"
    ROLLING = "rolling"
    UNCLEAR = "unclear"


class OpportunityStatus(StrEnum):
    NEEDS_REVIEW = "needs_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    HIDDEN = "hidden"


class SourceKind(StrEnum):
    RSS = "rss"
    HTML_LIST = "html_list"
    SITEMAP = "sitemap"
    MANUAL = "manual"


class FetchFrequency(StrEnum):
    DAILY = "daily"
    WEEKLY = "weekly"


class DigestFrequency(StrEnum):
    WEEKLY = "weekly"
    DAILY = "daily"


class SubscriberStatus(StrEnum):
    PENDING = "pending"  # signed up, email not yet confirmed
    ACTIVE = "active"
    UNSUBSCRIBED = "unsubscribed"


class RunKind(StrEnum):
    PIPELINE = "pipeline"
    EXPIRY = "expiry"
    DIGEST = "digest"
    SOCIAL = "social"


class RunStatus(StrEnum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ReportStatus(StrEnum):
    OPEN = "open"
    RESOLVED = "resolved"


class SubmissionStatus(StrEnum):
    NEW = "new"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class SocialPlatform(StrEnum):
    INSTAGRAM = "instagram"
    WHATSAPP = "whatsapp"


class SocialPostStatus(StrEnum):
    DRAFT = "draft"
    EXPORTED = "exported"
    PUBLISHED = "published"
    FAILED = "failed"


class RawItemStatus(StrEnum):
    NEW = "new"  # fetched, waiting for extraction
    PROCESSED = "processed"  # extraction done; html has been purged
    SKIPPED = "skipped"  # duplicate content or not an opportunity
    FAILED = "failed"
