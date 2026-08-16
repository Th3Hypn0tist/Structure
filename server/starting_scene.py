from __future__ import annotations

import copy
from typing import Any


def _contract(human: str) -> dict[str, Any]:
    return {
        "human": human,
        "human_revision": 1 if human else 0,
        "machine": {
            "status": "needs_generation" if human else "not_generated",
            "generated_from_human_revision": None,
            "data": None,
        },
    }


def _property(prop_id: str, property_type_ref: str, ruleset_ref: str, value: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": prop_id,
        "property_type_ref": property_type_ref,
        "ruleset_ref": ruleset_ref,
        "status": "unlocked",
        "value": value,
    }


def _type(prop_id: str, type_ref: str) -> dict[str, Any]:
    return _property(prop_id, "type", "RULESET_TYPE", {"type_ref": type_ref, "properties": {}})


def _data(prop_id: str, data_type_ref: str, **properties: Any) -> dict[str, Any]:
    return _property(prop_id, "data", "RULESET_DATA", {"data_type_ref": data_type_ref, "properties": properties})


def _event(prop_id: str, event_type_ref: str, **properties: Any) -> dict[str, Any]:
    return _property(prop_id, "event", "RULESET_EVENT", {"event_type_ref": event_type_ref, "properties": properties})


def _effect(prop_id: str, effect_type_ref: str, **properties: Any) -> dict[str, Any]:
    return _property(prop_id, "effect", "RULESET_EFFECT", {"effect_type_ref": effect_type_ref, "properties": properties})


def _function(
    prop_id: str,
    function_type_ref: str,
    *,
    input_refs: list[str] | None = None,
    output_refs: list[str] | None = None,
    **properties: Any,
) -> dict[str, Any]:
    value: dict[str, Any] = {"function_type_ref": function_type_ref, "properties": properties}
    if input_refs is not None:
        value["input_refs"] = input_refs
    if output_refs is not None:
        value["output_refs"] = output_refs
    return _property(prop_id, "function", "RULESET_FUNCTION", value)


def _link(
    prop_id: str,
    ruleset_ref: str,
    link_type_ref: str,
    parent_ref: str,
    child_ref: str,
    **properties: Any,
) -> dict[str, Any]:
    return _property(
        prop_id,
        "link",
        ruleset_ref,
        {
            "link_type_ref": link_type_ref,
            "parent_ref": parent_ref,
            "child_ref": child_ref,
            "properties": properties,
        },
    )


def _entity(
    entity_id: str,
    name: str,
    type_ref: str | None,
    position: list[float],
    description: str,
    human_contract: str,
    properties: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    items = list(properties or [])
    if type_ref is not None:
        items.insert(0, _type(f"TYPE_{entity_id}", type_ref))
    return {
        "id": entity_id,
        "name": name,
        "description": description,
        "status": "unlocked",
        "position": position,
        "contract": _contract(human_contract),
        "properties": items,
    }


STARTING_ENTITIES: list[dict[str, Any]] = [
    _entity(
        "ORDER_SERVICE",
        "Order Service",
        "service",
        [-6.0, 0.0, 0.0],
        "Receives order requests and creates the canonical New Order causal fanout.",
        "A valid order request may create a new order. Creating an order requires a known customer and available inventory. New Order inserts the order, reserves inventory and increments the customer's order count.",
        [
            _data("ORDER_REQUEST", "object", role="input", description="Incoming order request."),
            _function(
                "CREATE_ORDER",
                "command",
                input_refs=["ORDER_REQUEST", "CUSTOMERS_CUSTOMER_ID", "INVENTORY_AVAILABLE_QUANTITY"],
                output_refs=["EVENT_NEW_ORDER"],
                description="Validates an order request and emits New Order.",
            ),
            _event("EVENT_NEW_ORDER", "new_order", description="A new order has been accepted for processing."),
            _effect("EFFECT_INSERT_ORDER", "insert", description="Insert the order into the Orders dataset."),
            _effect("EFFECT_RESERVE_INVENTORY", "decrement", description="Reserve inventory for the accepted order."),
            _effect("EFFECT_INCREMENT_CUSTOMER_ORDER_COUNT", "increment", description="Increment the customer's order count."),
            _link("LINK_DEP_CUSTOMER_FOR_CREATE_ORDER", "RULESET_LINK_DEPENDENCY", "dependency", "CUSTOMERS_CUSTOMER_ID", "CREATE_ORDER", reason="create_order requires an addressable customer identity"),
            _link("LINK_DEP_INVENTORY_FOR_CREATE_ORDER", "RULESET_LINK_DEPENDENCY", "dependency", "INVENTORY_AVAILABLE_QUANTITY", "CREATE_ORDER", reason="create_order requires addressable inventory availability"),
            _link("LINK_INPUT_ORDER_REQUEST_TO_NEW_ORDER", "RULESET_LINK_EVENT_INPUT", "event_input", "ORDER_REQUEST", "EVENT_NEW_ORDER"),
            _link("LINK_NEW_ORDER_TO_INSERT_ORDER", "RULESET_LINK_EVENT_EFFECT", "event_effect", "EVENT_NEW_ORDER", "EFFECT_INSERT_ORDER"),
            _link("LINK_NEW_ORDER_TO_RESERVE_INVENTORY", "RULESET_LINK_EVENT_EFFECT", "event_effect", "EVENT_NEW_ORDER", "EFFECT_RESERVE_INVENTORY"),
            _link("LINK_NEW_ORDER_TO_INCREMENT_CUSTOMER", "RULESET_LINK_EVENT_EFFECT", "event_effect", "EVENT_NEW_ORDER", "EFFECT_INCREMENT_CUSTOMER_ORDER_COUNT"),
            _link("LINK_INSERT_ORDER_TO_RECORDSET", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT_INSERT_ORDER", "ORDERS_RECORDSET"),
            _link("LINK_INSERT_ORDER_TO_ORDER_ID", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT_INSERT_ORDER", "ORDERS_ORDER_ID"),
            _link("LINK_INSERT_ORDER_TO_CUSTOMER_ID", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT_INSERT_ORDER", "ORDERS_CUSTOMER_ID"),
            _link("LINK_INSERT_ORDER_TO_TOTAL", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT_INSERT_ORDER", "ORDERS_TOTAL"),
            _link("LINK_INSERT_ORDER_TO_STATUS", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT_INSERT_ORDER", "ORDERS_STATUS", value="pending"),
            _link("LINK_RESERVE_INVENTORY_TO_AVAILABLE", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT_RESERVE_INVENTORY", "INVENTORY_AVAILABLE_QUANTITY", operation="decrement_by_order_quantity"),
            _link("LINK_INCREMENT_CUSTOMER_TO_ORDER_COUNT", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT_INCREMENT_CUSTOMER_ORDER_COUNT", "CUSTOMERS_ORDER_COUNT", operation="increment"),
        ],
    ),
    _entity("ORDER_DB", "Order DB", "datastore", [0.0, 6.0, 0.0], "Physical datastore boundary for order data.", "Order DB stores the Sales schema."),
    _entity(
        "SALES_SCHEMA",
        "Sales Schema",
        "schema",
        [0.0, 3.0, 0.0],
        "Logical schema for sales data.",
        "Sales Schema defines the Orders dataset.",
        [_link("LINK_ORDER_DB_CONTAINS_SALES_SCHEMA", "RULESET_LINK_CONTAINMENT", "containment", "ORDER_DB", "SALES_SCHEMA")],
    ),
    _entity(
        "ORDERS",
        "Orders",
        "dataset",
        [0.0, 0.0, 0.0],
        "Canonical order dataset and its addressable data surfaces.",
        "Orders stores one record for each accepted order. Persisting a record may produce Order Persisted. Confirming persistence sets the order status to confirmed.",
        [
            _data("ORDERS_RECORDSET", "recordset", role="dataset_state"),
            _data("ORDERS_ORDER_ID", "string", nullable=False, role="primary_key"),
            _data("ORDERS_CUSTOMER_ID", "string", nullable=False, role="foreign_key"),
            _data("ORDERS_TOTAL", "decimal", nullable=False, unit_ref="currency"),
            _data("ORDERS_STATUS", "string", nullable=False, default="pending", allowed_values=["pending", "confirmed"]),
            _event("EVENT_ORDER_PERSISTED", "order_persisted", description="The new order has been persisted."),
            _effect("EFFECT_CONFIRM_ORDER", "set", description="Set the persisted order status to confirmed."),
            _link("LINK_SALES_SCHEMA_CONTAINS_ORDERS", "RULESET_LINK_CONTAINMENT", "containment", "SALES_SCHEMA", "ORDERS"),
            _link("LINK_RECORDSET_TO_ORDER_PERSISTED", "RULESET_LINK_EVENT_CONDITION", "event_condition", "ORDERS_RECORDSET", "EVENT_ORDER_PERSISTED", condition="record_inserted"),
            _link("LINK_ORDER_PERSISTED_TO_CONFIRM", "RULESET_LINK_EVENT_EFFECT", "event_effect", "EVENT_ORDER_PERSISTED", "EFFECT_CONFIRM_ORDER"),
            _link("LINK_CONFIRM_TO_STATUS", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT_CONFIRM_ORDER", "ORDERS_STATUS", value="confirmed"),
        ],
    ),
    _entity("INVENTORY_DB", "Inventory DB", "datastore", [6.0, 3.0, 0.0], "Physical datastore boundary for inventory data.", "Inventory DB stores the Inventory dataset."),
    _entity(
        "INVENTORY",
        "Inventory",
        "dataset",
        [6.0, 0.0, 0.0],
        "Inventory state and replenishment data.",
        "Inventory tracks available quantity. If available quantity falls below the configured threshold, Low Stock may create a replenishment request.",
        [
            _data("INVENTORY_AVAILABLE_QUANTITY", "integer", nullable=False, role="state"),
            _data("INVENTORY_REPLENISHMENT_QUEUE", "queue", role="output"),
            _event("EVENT_LOW_STOCK", "low_stock", description="Available quantity is below the replenishment threshold."),
            _effect("EFFECT_CREATE_REPLENISHMENT_REQUEST", "enqueue", description="Create a replenishment request."),
            _link("LINK_INVENTORY_DB_CONTAINS_INVENTORY", "RULESET_LINK_CONTAINMENT", "containment", "INVENTORY_DB", "INVENTORY"),
            _link("LINK_AVAILABLE_TO_LOW_STOCK", "RULESET_LINK_EVENT_CONDITION", "event_condition", "INVENTORY_AVAILABLE_QUANTITY", "EVENT_LOW_STOCK", condition="value < threshold"),
            _link("LINK_LOW_STOCK_TO_REPLENISH", "RULESET_LINK_EVENT_EFFECT", "event_effect", "EVENT_LOW_STOCK", "EFFECT_CREATE_REPLENISHMENT_REQUEST"),
            _link("LINK_REPLENISH_TO_QUEUE", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT_CREATE_REPLENISHMENT_REQUEST", "INVENTORY_REPLENISHMENT_QUEUE"),
        ],
    ),
    _entity("CUSTOMER_DB", "Customer DB", "datastore", [6.0, -3.0, 0.0], "Physical datastore boundary for customer data.", "Customer DB stores the Customers dataset."),
    _entity(
        "CUSTOMERS",
        "Customers",
        "dataset",
        [6.0, -6.0, 0.0],
        "Customer identity and derived customer state.",
        "Customers exposes the customer identity used by Order Service. Order count changes may recalculate the customer segment.",
        [
            _data("CUSTOMERS_CUSTOMER_ID", "string", nullable=False, role="primary_key"),
            _data("CUSTOMERS_ORDER_COUNT", "integer", nullable=False, default=0),
            _data("CUSTOMERS_SEGMENT", "string", nullable=True),
            _event("EVENT_CUSTOMER_SEGMENT_RECALCULATION", "customer_segment_recalculation", description="Customer segment must be recalculated."),
            _effect("EFFECT_UPDATE_CUSTOMER_SEGMENT", "set", description="Update the customer's derived segment."),
            _link("LINK_CUSTOMER_DB_CONTAINS_CUSTOMERS", "RULESET_LINK_CONTAINMENT", "containment", "CUSTOMER_DB", "CUSTOMERS"),
            _link("LINK_ORDER_COUNT_TO_SEGMENT_RECALC", "RULESET_LINK_EVENT_CONDITION", "event_condition", "CUSTOMERS_ORDER_COUNT", "EVENT_CUSTOMER_SEGMENT_RECALCULATION", condition="value_changed"),
            _link("LINK_SEGMENT_RECALC_TO_UPDATE", "RULESET_LINK_EVENT_EFFECT", "event_effect", "EVENT_CUSTOMER_SEGMENT_RECALCULATION", "EFFECT_UPDATE_CUSTOMER_SEGMENT"),
            _link("LINK_UPDATE_TO_SEGMENT", "RULESET_LINK_EFFECT_TARGET", "effect_target", "EFFECT_UPDATE_CUSTOMER_SEGMENT", "CUSTOMERS_SEGMENT"),
            _link("LINK_CUSTOMER_FK_RELATION", "RULESET_LINK_RELATION", "relation", "CUSTOMERS_CUSTOMER_ID", "ORDERS_CUSTOMER_ID", relation_type_ref="foreign_key"),
        ],
    ),
]


def starting_entities() -> list[dict[str, Any]]:
    return copy.deepcopy(STARTING_ENTITIES)
