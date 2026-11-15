"""Request and response shapes. Responses are plain dicts with the API's camelCase keys; these
TypedDicts describe them for editors and type checkers."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from typing_extensions import NotRequired, TypedDict

# POOLED_DELIVERY goes out in a wave on set days of the week, shared with deliveries going the same way: it needs
# ``window``, one PICKUP and one DROPOFF, and no ``dispatch``. BULK_DELIVERY was renamed
# POOLED_DELIVERY; create and quote refuse it (TASK_TYPE_RENAMED), older tasks keep it.
TaskType = Literal["PASSENGER_RIDE", "FOOD_DELIVERY", "PACKAGE_DELIVERY", "POOLED_DELIVERY", "BULK_DELIVERY", "ERRAND"]
# SendRelay adds statuses over time; one this version does not list arrives as its raw string.
# Handle the ones you know and treat any other as "still in progress".
TaskStatus = Union[
    Literal[
        "SCHEDULED",  # booked for a pickup time; SendRelay has not started looking yet
        "PENDING",
        "SEARCHING",  # still looking for a rider after the first offers
        "OFFERED",
        "ASSIGNED",
        "IN_PROGRESS",
        "COMPLETED",
        "CANCELLED",
        "FAILED",
        "PAYMENT_FAILED",
    ],
    str,
]
# When SendRelay looks for a rider; an unknown strategy arrives as its raw string.
DispatchStrategy = Union[Literal["IMMEDIATE", "WAIT_FOR_RIDER", "SCHEDULED"], str]
# A pooled delivery wave; an unknown one arrives as its raw string.
PooledWave = Union[Literal["MIDDAY"], str]
# Waiting for the wave, on a shared route, or going alone.
PooledState = Union[Literal["WAITING", "GROUPED", "SOLO"], str]
Priority = Literal["STANDARD", "URGENT"]
StageType = Literal["PICKUP", "DROPOFF"]
Weight = Literal["LIGHT", "STANDARD", "HEAVY", "FREIGHT"]
Size = Literal["ENVELOPE", "BOX", "LARGE_BOX", "FREIGHT"]
VehicleType = Literal["BICYCLE", "MOTORCYCLE", "TRICYCLE", "CAR", "VAN", "TRUCK"]
WebhookMode = Literal["test", "live"]
PresenceResolution = Literal["BLOCK", "NEIGHBOURHOOD", "DISTRICT"]


class Location(TypedDict):
    latitude: float
    longitude: float
    address: str
    countryCode: NotRequired[str]  # ISO 3166-1 alpha-2, e.g. "NG"; not used in pricing yet
    postalCode: NotRequired[str]  # not used in pricing yet


class Item(TypedDict):
    name: str
    reference: NotRequired[str]  # your own parcel id, followed across legs later
    estimatedValue: int
    estimatedWeight: Weight
    estimatedSize: Size
    description: NotRequired[str]
    specialInstructions: NotRequired[str]


class Passenger(TypedDict):
    name: str
    contactInfo: NotRequired[str]
    specialNeeds: NotRequired[str]
    luggageCount: NotRequired[int]


class Stage(TypedDict):
    type: StageType
    location: Location
    instructions: NotRequired[str]
    items: NotRequired[List[Item]]
    passengers: NotRequired[List[Passenger]]
    status: NotRequired[str]
    completedAt: NotRequired[Optional[str]]


class Preferences(TypedDict, total=False):
    minRating: float
    hasBox: bool
    hasRefrigeration: bool
    hasAirConditioning: bool
    vehicleType: List[VehicleType]
    allowedOrganisations: List[str]
    blockedOrganisations: List[str]
    allowIndependentRiders: bool


class DispatchRequest(TypedDict):
    """``dispatch`` on create and quote; leave it out for IMMEDIATE. Part of the quote lock.

    - ``{"strategy": "IMMEDIATE"}``: offer to nearby riders now (about two minutes).
    - ``{"strategy": "WAIT_FOR_RIDER", "maxWaitMinutes": 120}``: then keep offering as riders come
      online nearby, for 5-720 minutes (food 5-45).
    - ``{"strategy": "SCHEDULED", "pickupAt": "2026-11-05T15:00:00+01:00"}``: book 45 minutes to
      7 days ahead, priced for then and held now; ``pickupWindowMinutes`` defaults to 30 (max 120).
    """

    strategy: DispatchStrategy
    maxWaitMinutes: NotRequired[int]
    pickupAt: NotRequired[str]
    pickupWindowMinutes: NotRequired[int]


class TaskDispatch(TypedDict):
    """The dispatch block on every task: the strategy and its search window."""

    strategy: DispatchStrategy
    maxWaitMinutes: Optional[int]
    pickupAt: Optional[str]
    pickupWindowMinutes: Optional[int]
    searchStartsAt: str
    searchExpiresAt: Optional[str]  # None for IMMEDIATE: the offer waves decide
    offerRounds: int


class PooledWindowRequest(TypedDict):
    """``window`` on create and quote, POOLED_DELIVERY only. Leave ``date`` (YYYY-MM-DD, Lagos) out
    for the next wave still open. Quote without a window to see the upcoming waves."""

    wave: PooledWave
    date: NotRequired[str]


class TaskPooledWindow(TypedDict):
    """A pooled delivery's ``window`` on the task."""

    wave: PooledWave
    date: str
    bookBy: str  # last moment to book, and to cancel for free
    pickupFrom: str
    pickupTo: str
    deliverBy: str
    state: PooledState
    sharedWith: Optional[int]  # other deliveries on its route (never who they are)
    plannedPickupAt: Optional[str]
    plannedDeliveryAt: Optional[str]
    # Stops the rider makes before this delivery's next stop, while that is known.
    stopsBefore: NotRequired[Optional[int]]


class PooledQuotePricing(TypedDict):
    kind: Literal["RANGE"]
    maxTotal: int  # the most you pay, held at booking
    total: int  # the expected price, from deliveries already booked nearby
    minTotal: int  # the least you pay


class PooledQuoteWindow(TypedDict):
    """An upcoming wave in a pooled quote, with this delivery's price range in it."""

    wave: PooledWave
    date: str
    status: str  # OPEN, or FULL (create refuses it with WAVE_FULL)
    bookBy: str
    pickupFrom: str
    pickupTo: str
    deliverBy: str
    pricing: PooledQuotePricing
    quoteId: str  # pass to create with this window
    expiresAt: str


class TaskQuoteRequest(TypedDict):
    taskType: TaskType
    stages: List[Stage]
    priority: NotRequired[Priority]
    preferences: NotRequired[Preferences]
    dispatch: NotRequired[DispatchRequest]  # not on POOLED_DELIVERY
    # POOLED_DELIVERY only, and required there on create: the wave to book into.
    window: NotRequired[PooledWindowRequest]
    # Insurance on the items' declared values. On by default; False turns it off for this task, so
    # no premium is charged and loss or damage is not covered. Send the same value you quoted.
    insured: NotRequired[bool]


class CreateTaskRequest(TaskQuoteRequest):
    autoAssign: NotRequired[bool]
    paymentMethod: NotRequired[Literal["WALLET", "CARD"]]
    notes: NotRequired[str]
    externalId: NotRequired[str]
    quoteId: NotRequired[str]
    completionCode: NotRequired[Dict[str, Any]]
    # Test keys. SEARCH_THEN_ASSIGNED and SEARCH_EXPIRED need WAIT_FOR_RIDER or SCHEDULED;
    # POOLING_SOLO (POOLED_DELIVERY only) sends the delivery alone at its maximum price.
    simulationOutcome: NotRequired[str]


class TaskLiveEta(TypedDict):
    """How far the rider is from the stop they are heading to, from their navigation route."""

    stageIndex: int
    seconds: int
    meters: int
    arrivesAt: str
    updatedAt: str


class TaskRating(TypedDict):
    rating: int
    comment: Optional[str]
    createdAt: str


class TaskRequirementsVehicle(TypedDict):
    vehicleType: str
    # "BOX", "REFRIGERATION" or "AIR_CONDITIONING"; treat others as equipment you can't check.
    equipment: List[str]


class TaskRequirements(TypedDict):
    """The vehicles SendRelay looks for and the equipment a rider on each needs."""

    vehicles: List[TaskRequirementsVehicle]


class Task(TypedDict):
    id: str
    developerId: str
    riderId: Optional[str]
    externalId: Optional[str]
    status: TaskStatus
    taskType: TaskType
    priority: Priority
    autoAssign: bool
    currentStageIndex: Optional[int]
    stages: List[Stage]
    deliveryFee: int
    totalFee: int
    paymentMethod: str
    paymentStatus: Optional[str]
    createdAt: str
    updatedAt: str
    completionCodeRequired: bool
    completionCodeLength: Optional[int]
    # Goes up with every event about the task and matches events' data["revision"]. 0 before the first.
    revision: int
    # Currency of every amount, in minor units (kobo for NGN).
    currency: Literal["NGN"]
    # A completion photo is required at every DROPOFF.
    requirePhoto: NotRequired[bool]
    rider: NotRequired[Dict[str, Any]]
    completionCode: NotRequired[Optional[Dict[str, Any]]]
    dispatch: TaskDispatch
    requirements: NotRequired[TaskRequirements]
    # POOLED_DELIVERY only: its wave and where it stands.
    window: NotRequired[TaskPooledWindow]
    # Pooled tasks add kind "RANGE", maxTotal, minTotal, finalTotal and finalAt.
    pricing: NotRequired[Optional[Dict[str, Any]]]


class SimulateAdvanceResponse(TypedDict):
    message: str
    taskId: str
    status: TaskStatus  # still SCHEDULED; it moves to PENDING within seconds
    searchStartsAt: str
    searchExpiresAt: str


class GetTaskResponse(TypedDict):
    task: Task
    rating: Optional[TaskRating]
    liveEta: Optional[TaskLiveEta]


class TaskListItem(TypedDict):
    id: str
    status: TaskStatus
    taskType: TaskType
    totalFee: int
    createdAt: str
    updatedAt: NotRequired[str]
    revision: NotRequired[int]
    currency: NotRequired[Literal["NGN"]]


class ListTasksResponse(TypedDict):
    data: List[TaskListItem]
    hasMore: bool
    cursor: Optional[str]


class CreateTaskResponse(TypedDict):
    message: str
    task: Task
    pricing: Dict[str, Any]
    idempotency: Dict[str, Any]


class TaskQuoteResponse(TypedDict):
    total: int
    subtotal: int
    tax: int
    platformFee: int
    # The premium (0 when not insured), included in subtotal and total, and the value it covers.
    insuranceFee: int
    insuredValue: int
    quoteId: str
    expiresAt: str
    quoteTtlSeconds: int
    # What the task will need, as create will store it.
    requirements: NotRequired[TaskRequirements]
    # POOLED_DELIVERY: the upcoming waves, each with its own price range and quoteId.
    windows: NotRequired[List[PooledQuoteWindow]]


class CancelTaskResponse(TypedDict):
    message: str
    taskId: str
    status: Literal["CANCELLED"]


class Webhook(TypedDict):
    id: str
    url: str
    mode: WebhookMode
    events: List[str]
    createdAt: str
    usage: Dict[str, Any]
    description: NotRequired[str]


class CreateWebhookResponse(TypedDict):
    id: str
    url: str
    mode: WebhookMode
    events: List[str]
    secret: str


class ListWebhooksResponse(TypedDict):
    data: List[Webhook]
    hasMore: bool
    cursor: Optional[str]


class WebSocketToken(TypedDict):
    token: str
    expiresIn: int
    expiresAt: str
    scope: List[str]


class PresenceResponse(TypedDict):
    mode: WebhookMode
    simulated: bool
    resolution: PresenceResolution
    cells: List[Dict[str, Any]]
    totals: Dict[str, Any]
    generatedAt: str
    refreshAfterSeconds: int
    # With ``taskType``: what the counted riders have, as the quote would return it.
    requirements: NotRequired[TaskRequirements]


class RelayEvent(TypedDict):
    """An event exactly as its webhook carried it. Task events carry ``data["revision"]``."""

    id: str
    type: str
    version: str
    timestamp: str
    data: Dict[str, Any]
    metadata: Dict[str, Any]


class ListEventsResponse(TypedDict):
    data: List[RelayEvent]
    hasMore: bool
    cursor: Optional[str]


class TaskEventsResponse(TypedDict):
    data: List[RelayEvent]


class RedeliverWebhookResponse(TypedDict):
    webhookId: str
    eventId: str
    queued: Literal[True]


class TrackingLinkResponse(TypedDict):
    """A hosted tracking page to send your customer; SendRelay never contacts them itself."""

    url: str
    expiresAt: str
    stageIndex: Optional[int]


# Insurance claims, for insured goods lost, stolen or damaged after collection. Amounts in kobo.
ClaimIncidentType = Literal["LOST", "STOLEN", "DAMAGED"]
ClaimStatus = Union[
    Literal["SUBMITTED", "NEEDS_INFO", "WITH_INSURER", "APPROVED", "DECLINED", "PAID", "WITHDRAWN"], str
]
ClaimFileContentType = Literal["image/jpeg", "image/png", "image/webp", "application/pdf"]


class ClaimFile(TypedDict):
    """A file from ``claims.create_upload``, by its ``key``, with the name to show for it."""

    key: str
    name: str


class Claim(TypedDict):
    id: str
    reference: str
    status: ClaimStatus
    incidentType: ClaimIncidentType
    incidentDate: str
    claimedAmount: int
    approvedAmount: Optional[int]
    description: str
    files: List[Dict[str, str]]
    infoRequest: Optional[str]
    decisionReason: Optional[str]
    filedOn: Optional[str]
    decidedOn: Optional[str]
    paidOn: Optional[str]


class ClaimState(TypedDict):
    """A task's claim, or whether you can file one (``can_file``/``reason``) and until when."""

    claim: Optional[Claim]
    canFile: bool
    reason: Optional[str]
    insuredValue: Optional[int]
    certificateNumber: Optional[str]
    closesOn: Optional[str]


class ClaimUpload(TypedDict):
    """PUT the file to ``uploadUrl`` with ``Content-Type: contentType`` before ``expiresAt``, then send ``key``."""

    uploadUrl: str
    key: str
    contentType: ClaimFileContentType
    maxFileSize: int
    expiresAt: str
