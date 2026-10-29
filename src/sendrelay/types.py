"""Request and response shapes. Responses are plain dicts with the API's camelCase keys; these
TypedDicts describe them for editors and type checkers."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from typing_extensions import NotRequired, TypedDict

TaskType = Literal["PASSENGER_RIDE", "FOOD_DELIVERY", "PACKAGE_DELIVERY", "BULK_DELIVERY", "ERRAND"]
TaskStatus = Literal[
    "PENDING", "OFFERED", "ASSIGNED", "IN_PROGRESS", "COMPLETED", "CANCELLED", "FAILED", "PAYMENT_FAILED"
]
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


class Item(TypedDict):
    name: str
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


class TaskQuoteRequest(TypedDict):
    taskType: TaskType
    stages: List[Stage]
    priority: NotRequired[Priority]
    preferences: NotRequired[Preferences]


class CreateTaskRequest(TaskQuoteRequest):
    autoAssign: NotRequired[bool]
    paymentMethod: NotRequired[Literal["WALLET", "CARD"]]
    notes: NotRequired[str]
    externalId: NotRequired[str]
    quoteId: NotRequired[str]
    completionCode: NotRequired[Dict[str, Any]]
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
