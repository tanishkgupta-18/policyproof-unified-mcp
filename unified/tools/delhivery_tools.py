"""Delhivery Mock Logistics Tools for PolicyProof Unified MCP.

Exposes deterministic logistics simulation tools for AgenticOrg:
- Pincode serviceability
- Package shipment creation
- Shipment tracking
- Pickup request creation

Contains NO LLM logic and NO autonomous decision making.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from mock_rules import (
    check_pincode_serviceability,
    create_pickup_request,
    create_shipment,
    track_shipment,
)

logger = logging.getLogger("policyproof-unified-mcp.delhivery_tools")


def delhivery_pincode_serviceability(pincode: str) -> Dict[str, Any]:
    """Check whether a destination pincode is serviceable by Delhivery for Prepaid, COD, and Reverse Pickup.

    Mirrors documented endpoint: GET /c/api/pin-codes/json/?filter_codes={pincode}

    Args:
        pincode: 6-digit Indian postal code to check (e.g. '560001', '110001', '400001').

    Returns:
        Structured dictionary with serviceability flag, payment/pickup capabilities, and routing hub.
    """
    logger.info("Checking pincode serviceability for: %s", pincode)
    return check_pincode_serviceability(pincode=pincode)


def delhivery_create_shipment(
    name: str,
    add: str,
    pin: str,
    city: str,
    state: str,
    phone: str,
    order: str,
    country: str = "India",
    payment_mode: str = "Prepaid",
    return_pin: Optional[str] = None,
    return_city: Optional[str] = None,
    return_phone: Optional[str] = None,
    return_add: Optional[str] = None,
    return_state: Optional[str] = None,
    return_country: Optional[str] = "India",
    products_desc: Optional[str] = "Standard Goods",
    hsn_code: Optional[str] = None,
    cod_amount: Optional[str] = "0",
    order_date: Optional[str] = None,
    total_amount: Optional[str] = "0.00",
    seller_add: Optional[str] = None,
    seller_name: Optional[str] = None,
    seller_inv: Optional[str] = None,
    quantity: Optional[str] = "1",
    waybill: Optional[str] = "",
    shipment_width: Optional[str] = "10",
    shipment_height: Optional[str] = "10",
    weight: Optional[str] = "0.5",
    shipping_mode: Optional[str] = "Surface",
    address_type: Optional[str] = "home",
) -> Dict[str, Any]:
    """Create a package shipment in Delhivery network.

    Mirrors documented endpoint: POST /api/cmu/create.json

    Required Fields:
        name: Consignee / recipient full name
        add: Consignee destination delivery address
        pin: Destination 6-digit postal pincode
        city: Destination city name
        state: Destination state name
        phone: Consignee contact telephone number
        order: Merchant unique order reference ID

    Optional Fields:
        country: Destination country (default 'India')
        payment_mode: Payment type: 'Prepaid' or 'COD' (default 'Prepaid')
        return_pin: Return warehouse 6-digit pincode in case of RTO
        return_city: Return warehouse city
        return_phone: Return contact telephone
        return_add: Return warehouse full address
        return_state: Return warehouse state
        return_country: Return warehouse country (default 'India')
        products_desc: Description of package products (default 'Standard Goods')
        hsn_code: Harmonized System of Nomenclature code
        cod_amount: Cash-on-delivery amount to collect (default '0')
        order_date: Order placement ISO date/time string
        total_amount: Total declared invoice amount (default '0.00')
        seller_add: Registered seller warehouse address
        seller_name: Registered seller trade name
        seller_inv: Merchant invoice number
        quantity: Number of product pieces (default '1')
        waybill: Pre-allocated AWB waybill number if available
        shipment_width: Package width in cm (default '10')
        shipment_height: Package height in cm (default '10')
        weight: Package gross dead weight in kg (default '0.5')
        shipping_mode: Shipping mode: 'Surface' or 'Express' (default 'Surface')
        address_type: Destination address classification: 'home' or 'office' (default 'home')

    Returns:
        Structured dictionary with creation status, waybill number, order ID, and raw Delhivery payload.
    """
    logger.info("Creating shipment for order: %s, pin: %s (POST /api/cmu/create.json)", order, pin)
    return create_shipment(
        name=name,
        add=add,
        pin=pin,
        city=city,
        state=state,
        phone=phone,
        order=order,
        country=country,
        payment_mode=payment_mode,
        return_pin=return_pin,
        return_city=return_city,
        return_phone=return_phone,
        return_add=return_add,
        return_state=return_state,
        return_country=return_country,
        products_desc=products_desc,
        hsn_code=hsn_code,
        cod_amount=cod_amount,
        order_date=order_date,
        total_amount=total_amount,
        seller_add=seller_add,
        seller_name=seller_name,
        seller_inv=seller_inv,
        quantity=quantity,
        waybill=waybill,
        shipment_width=shipment_width,
        shipment_height=shipment_height,
        weight=weight,
        shipping_mode=shipping_mode,
        address_type=address_type,
    )


def delhivery_track_shipment(waybill: str) -> Dict[str, Any]:
    """Track shipment lifecycle status and checkpoint scan history by Delhivery waybill number.

    Mirrors documented endpoint: GET /api/v1/packages/json/?waybill={waybill}

    Supported Lifecycle States:
        Manifested, Ready for Pickup, In Transit, Out for Delivery,
        Delivered, Cancelled / RTO, Lost.

    Args:
        waybill: 13-digit Delhivery AWB waybill tracking number or test trigger.

    Returns:
        Structured dictionary with waybill, status, scan history, and raw response.
    """
    logger.info("Tracking shipment for waybill: %s (GET /api/v1/packages/json/)", waybill)
    return track_shipment(waybill=waybill)


def delhivery_create_pickup_request(
    pickup_location: str,
    pickup_date: str,
    pickup_slot: str,
    shipment_waybills: List[str],
) -> Dict[str, Any]:
    """Create a Delhivery pickup request for manifesting shipments.

    Mirrors documented endpoint: POST /fm/request/new/

    Supported Pickup Lifecycle States:
        Scheduled, Out for Pickup, Picked, Cancelled.

    Args:
        pickup_location: Registered pickup warehouse/facility location name (Required)
        pickup_date: Scheduled pickup date in YYYY-MM-DD format (Required)
        pickup_slot: Preferred pickup window slot (e.g. '14:00 - 18:00') (Required)
        shipment_waybills: List of Delhivery waybills to be handed over (Required)

    Returns:
        Structured dictionary with pickup request ID, status, location, slot, and raw payload.
    """
    logger.info("Creating pickup request at '%s' on %s (POST /fm/request/new/)", pickup_location, pickup_date)
    return create_pickup_request(
        pickup_location=pickup_location,
        pickup_date=pickup_date,
        pickup_slot=pickup_slot,
        shipment_waybills=shipment_waybills,
    )
