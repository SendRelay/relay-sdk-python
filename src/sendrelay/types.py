"""Request and response shapes. Responses are plain dicts with the API's camelCase keys; these
TypedDicts describe them for editors and type checkers."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from typing_extensions import NotRequired, TypedDict

TaskType = Literal["PASSENGER_RIDE", "FOOD_DELIVERY", "PACKAGE_DELIVERY", "BULK_DELIVERY", "ERRAND"]
# Relay adds statuses over time; one this version does not list arrives as its raw string.
# Handle the ones you know and treat any other as "still in progress".
TaskStatus = Union[
    Literal[
        "SCHEDULED",  # booked for a pickup time; Relay has not started looking yet
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
# When Relay looks for a rider; an unknown strategy arrives as its raw string.
DispatchStrategy = Union[Literal["IMMEDIATE", "WAIT_FOR_RIDER", "SCHEDULED"], str]
Priority = Literal["STANDARD", "URGENT"]
StageType = Literal["PICKUP", "DROPOFF"]
Weight = Literal["LIGHT", "STANDARD", "HEAVY", "FREIGHT"]
Size = Literal["ENVELOPE", "BOX", "LARGE_BOX", "FREIGHT"]
VehicleType = Literal["BICYCLE", "BIKE", "MOTORCYCLE", "TRICYCLE", "CAR", "VAN", "TRUCK"]
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


class TaskQuoteRequest(TypedDict):
    taskType: TaskType
    stages: List[Stage]
    priority: NotRequired[Priority]
    preferences: NotRequired[Preferences]
    dispatch: NotRequired[DispatchRequest]
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
    # Test keys. SEARCH_THEN_ASSIGNED and SEARCH_EXPIRED need WAIT_FOR_RIDER or SCHEDULED.
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
    rider: NotRequired[Dict[str, Any]]
    completionCode: NotRequired[Optional[Dict[str, Any]]]
    dispatch: TaskDispatch


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
