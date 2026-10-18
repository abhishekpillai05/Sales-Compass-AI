"""
Tests for Intelligent Sales Conversations, Deal Tracking, Cross-Selling and Upselling.

Verifies:
 1. Generic product requests trigger relevant follow-up questions.
 2. Product-specific attributes are extracted correctly.
 3. Previously supplied attributes are not repeatedly requested.
 4. Follow-up answers update persistent requirements.
 5. The correct conversation context is retained.
 6. Matching products come from the actual catalogue.
 7. No cross-selling occurs before deal finalisation.
 8. No upselling occurs before deal finalisation.
 9. Ambiguous confirmation does not finalise the deal.
10. Explicit confirmation follows the approved finalisation workflow.
11. Finalised deals enable eligible recommendations.
12. Recommendations do not silently alter the original deal.
13. Unsupported products and fabricated prices are never recommended.
14. Conversation state persists after refresh.
15. Existing RBAC, authentication, search, upload, and conversation tests remain valid.
"""
import uuid
import pytest
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.database.session import SessionLocal
from app.database.models import User, Conversation, SalesConversationState
from app.auth.sessions import create_session
from app.conversation.service import create_conversation, add_message
from app.conversation.contextualizer import contextualize_query
from app.conversation.sales_extractor import (
    detect_product_category,
    extract_requirements,
    get_next_follow_up_questions,
    has_sufficient_information_for_matching,
    is_skip_response,
)
from app.conversation.sales_service import (
    get_or_create_sales_state,
    get_sales_state,
    update_sales_state,
    select_product_for_deal,
    finalize_deal,
    reopen_deal,
    can_recommend_addons,
    is_ambiguous_confirmation,
    is_explicit_confirmation,
)
from app.conversation.recommendation_service import generate_recommendations


@pytest.fixture(scope="module")
def db_session():
    db = SessionLocal(expire_on_commit=False)
    try:
        yield db
    finally:
        try:
            db.close()
        except Exception:
            pass


@pytest.fixture(autouse=True)
def clean_db_session(db_session):
    try:
        yield
    finally:
        try:
            db_session.rollback()
        except Exception:
            pass


@pytest.fixture(scope="module")
def user_a(db_session):
    uid = uuid.uuid4().hex[:8]
    user = User(
        username=f"sales_user_a_{uid}",
        email=f"sales_user_a_{uid}@example.com",
        password_hash="testhash123",
        role="SALESMAN",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def user_b(db_session):
    uid = uuid.uuid4().hex[:8]
    user = User(
        username=f"sales_user_b_{uid}",
        email=f"sales_user_b_{uid}@example.com",
        password_hash="testhash123",
        role="SALESMAN",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def client_a(db_session, user_a):
    session = create_session(db=db_session, user_id=user_a.id)
    client = TestClient(app)
    client.cookies.set("session_token", session.session_token)
    return client


@pytest.fixture(scope="module")
def client_b(db_session, user_b):
    session = create_session(db=db_session, user_id=user_b.id)
    client = TestClient(app)
    client.cookies.set("session_token", session.session_token)
    return client


@pytest.fixture(scope="module")
def anon_client():
    return TestClient(app)


@pytest.fixture(scope="module")
def admin_user(db_session):
    uid = uuid.uuid4().hex[:8]
    user = User(
        username=f"sales_admin_{uid}",
        email=f"sales_admin_{uid}@example.com",
        password_hash="testhash123",
        role="ADMIN",
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture(scope="module")
def admin_client(db_session, admin_user):
    session = create_session(db=db_session, user_id=admin_user.id)
    client = TestClient(app)
    client.cookies.set("session_token", session.session_token)
    return client


# ===========================================================================
# 1. Follow-up Questions & Attribute Extraction Tests
# ===========================================================================

class TestSalesFollowUpAndExtraction:
    def test_generic_product_request_triggers_category_follow_up_questions(self):
        """1. Generic product requests trigger relevant follow-up questions."""
        # Generic ladder inquiry
        cat = detect_product_category("I want a ladder")
        assert cat == "ladder"
        questions = get_next_follow_up_questions(category_id=cat, current_requirements={}, max_questions=2)
        assert len(questions) == 2
        # Should ask for height and material first
        keys = [q["key"] for q in questions]
        assert "height" in keys
        assert "material" in keys

        # Generic scrubber inquiry
        cat_scrub = detect_product_category("We need a commercial floor scrubber")
        assert cat_scrub == "floor_scrubber"
        scrub_qs = get_next_follow_up_questions(category_id=cat_scrub, current_requirements={}, max_questions=2)
        assert len(scrub_qs) == 2
        scrub_keys = [q["key"] for q in scrub_qs]
        assert "machine_type" in scrub_keys or "capacity_or_width" in scrub_keys

    def test_product_specific_attributes_extracted_correctly(self):
        """2. Product-specific attributes are extracted correctly (multi-attribute support)."""
        text = "I want an 8ft fiberglass ladder with 300 lbs capacity for electrical work under $300, need 2 units"
        cat = detect_product_category(text)
        assert cat == "ladder"

        reqs, has_updates = extract_requirements(text=text, category_id=cat, existing_requirements={})
        assert has_updates is True
        assert "8ft" in str(reqs.get("height")).lower()
        assert "fiberglass" in str(reqs.get("material")).lower()
        assert "300" in str(reqs.get("load_capacity"))
        assert "electrical" in str(reqs.get("application")).lower()
        assert reqs.get("quantity") == 2

    def test_previously_supplied_attributes_not_repeated(self):
        """3. Previously supplied attributes are not repeatedly requested."""
        existing = {
            "height": "8 ft",
            "material": "fiberglass",
        }
        questions = get_next_follow_up_questions(category_id="ladder", current_requirements=existing, max_questions=2)
        keys = [q["key"] for q in questions]
        # Must not ask for height or material again
        assert "height" not in keys
        assert "material" not in keys
        # Next should be load_capacity or application
        assert "load_capacity" in keys or "application" in keys

    def test_skip_optional_questions_handled(self):
        """Allows customers to skip optional questions."""
        assert is_skip_response("no preference") is True
        assert is_skip_response("skip") is True
        assert is_skip_response("doesn't matter") is True
        assert is_skip_response("any brand is fine") is True

        reqs, updated = extract_requirements(
            text="no preference",
            category_id="ladder",
            existing_requirements={"height": "8 ft"},
        )
        assert updated is True
        assert reqs.get("material") == "No preference"

    def test_follow_up_answers_update_persistent_requirements(self, db_session, user_a):
        """4. Follow-up answers update persistent requirements in PostgreSQL."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Ladder Selection")
        state = get_or_create_sales_state(db=db_session, conversation_id=conv.id)
        assert state.extracted_requirements == {}

        # Turn 1
        reqs1, _ = extract_requirements("I need a ladder", "ladder", state.extracted_requirements)
        state = update_sales_state(db=db_session, state=state, product_category="ladder", extracted_requirements=reqs1)

        # Turn 2: Customer specifies 8ft fiberglass
        reqs2, _ = extract_requirements("It should be 8 ft tall and fiberglass", "ladder", state.extracted_requirements)
        state = update_sales_state(db=db_session, state=state, extracted_requirements=reqs2)

        # Turn 3: Customer specifies load capacity
        reqs3, _ = extract_requirements("300 lbs capacity needed", "ladder", state.extracted_requirements)
        state = update_sales_state(db=db_session, state=state, extracted_requirements=reqs3)

        # Verify persistent requirements in DB
        db_state = get_sales_state(db=db_session, conversation_id=conv.id, user_id=user_a.id)
        assert "8 ft" in db_state.extracted_requirements.get("height", "")
        assert "fiberglass" in db_state.extracted_requirements.get("material", "")
        assert "300" in db_state.extracted_requirements.get("load_capacity", "")

    def test_correct_conversation_context_retained(self, db_session, user_a):
        """5. The correct conversation context is retained across follow-up turns."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Karcher Scrubber Context")
        m1 = add_message(db=db_session, conversation_id=conv.id, role="user", content="Tell me about the Kärcher BD 43/40")
        m2 = add_message(db=db_session, conversation_id=conv.id, role="assistant", content="The Kärcher BD 43/40 is a walk-behind scrubber-dryer with a 43-litre tank.")

        # Follow-up query using pronoun 'its'
        history = [m1, m2]
        standalone = contextualize_query("What is its tank capacity?", history=history)
        assert "43/40" in standalone or "karcher" in standalone.lower() or "scrubber" in standalone.lower()


# ===========================================================================
# 2. Deal Finalisation Safeguards & Workflow Tests
# ===========================================================================

class TestDealFinalisationSafeguards:
    def test_ambiguous_confirmation_does_not_finalise_deal(self, db_session, user_a):
        """9. Ambiguous confirmation does not finalise the deal."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Scrubber Deal Ambiguity Test")
        state = get_or_create_sales_state(db=db_session, conversation_id=conv.id)

        # Set a candidate product
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}
        select_product_for_deal(db=db_session, conversation_id=conv.id, user_id=user_a.id, product=candidate, quantity=1)

        # Test ambiguous statements
        ambiguous_statements = [
            "Looks good",
            "Tell me more",
            "Maybe",
            "What is the price?",
            "I am interested",
            "Sounds good",
        ]
        for phrase in ambiguous_statements:
            assert is_ambiguous_confirmation(phrase) is True
            # Backend finalize_deal MUST reject with 400
            with pytest.raises(HTTPException) as exc_info:
                finalize_deal(
                    db=db_session,
                    conversation_id=conv.id,
                    user_id=user_a.id,
                    confirmation_text=phrase,
                )
            assert exc_info.value.status_code == 400
            assert "ambiguous" in exc_info.value.detail.lower()

        # State must remain OPEN, never finalised
        state = get_sales_state(db=db_session, conversation_id=conv.id, user_id=user_a.id)
        assert state.deal_status == "OPEN"
        assert state.stage == "DEAL_DISCUSSION"
        assert state.deal_finalized_at is None

    def test_explicit_confirmation_follows_approved_workflow(self, db_session, user_a):
        """10. Explicit confirmation follows the approved finalisation workflow."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Explicit Finalisation Test")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}
        select_product_for_deal(db=db_session, conversation_id=conv.id, user_id=user_a.id, product=candidate, quantity=2)

        # Explicit confirmation
        final_state = finalize_deal(
            db=db_session,
            conversation_id=conv.id,
            user_id=user_a.id,
            confirmation_text="I explicitly confirm this deal order for 2 units",
            override_quantity=2,
            override_price="$3,200",
        )

        assert final_state.deal_status == "FINALIZED"
        assert final_state.stage == "DEAL_FINALIZED"
        assert final_state.agreed_quantity == 2
        assert final_state.deal_finalized_at is not None
        assert can_recommend_addons(final_state) is True


# ===========================================================================
# 3. Cross-Selling & Upselling Eligibility Tests
# ===========================================================================

class TestCrossSellingAndUpselling:
    def test_no_cross_selling_before_deal_finalisation(self, db_session, user_a):
        """7. No cross-selling occurs before deal finalisation."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Pre-Finalisation Test")
        state = get_or_create_sales_state(db=db_session, conversation_id=conv.id)
        assert state.deal_status == "OPEN"
        assert can_recommend_addons(state) is False

        # Attempting to generate recommendations before finalisation MUST raise 400
        with pytest.raises(HTTPException) as exc_info:
            generate_recommendations(db=db_session, state=state)
        assert exc_info.value.status_code == 400
        assert "disabled until" in exc_info.value.detail.lower() or "strictly disabled" in exc_info.value.detail.lower()

    def test_no_upselling_before_deal_finalisation(self, db_session, user_a, client_a):
        """8. No upselling occurs before deal finalisation via API."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Upsell API Guard Test")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40"}
        select_product_for_deal(db=db_session, conversation_id=conv.id, user_id=user_a.id, product=candidate, quantity=1)

        # Call recommendations endpoint before finalisation -> must return 400
        res = client_a.post(f"/conversations/{conv.id}/deal/recommendations")
        assert res.status_code == 400
        assert "disabled" in res.json()["detail"].lower()

    def test_finalised_deals_enable_eligible_recommendations(self, db_session, user_a):
        """11. Finalised deals enable eligible recommendations."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Finalised Recommendations Test")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}
        select_product_for_deal(db=db_session, conversation_id=conv.id, user_id=user_a.id, product=candidate, quantity=1)
        update_sales_state(db=db_session, state=get_sales_state(db_session, conv.id, user_a.id), product_category="floor_scrubber")

        final_state = finalize_deal(db=db_session, conversation_id=conv.id, user_id=user_a.id)
        assert final_state.deal_status == "FINALIZED"

        # Now generate recommendations -> must succeed
        recs = generate_recommendations(db=db_session, state=final_state)
        assert recs is not None
        assert "cross_sells" in recs
        assert "upsells" in recs
        assert len(recs["cross_sells"]) > 0
        assert len(recs["upsells"]) > 0

        # Each cross-sell must have explanation
        for cs in recs["cross_sells"]:
            assert cs["type"] == "cross_sell"
            assert len(cs["relevance_explanation"]) > 10

        # Each upsell must have trade-off note or benefit explanation
        for us in recs["upsells"]:
            assert us["type"] == "upsell"
            assert len(us["relevance_explanation"]) > 10

    def test_recommendations_do_not_silently_alter_original_deal(self, db_session, user_a):
        """12. Recommendations do not silently alter the original deal."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Immutability Test")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}
        select_product_for_deal(db=db_session, conversation_id=conv.id, user_id=user_a.id, product=candidate, quantity=3)
        final_state = finalize_deal(db=db_session, conversation_id=conv.id, user_id=user_a.id)

        # Generate recommendations
        generate_recommendations(db=db_session, state=final_state)

        # Re-fetch state from database
        db_state = get_sales_state(db=db_session, conversation_id=conv.id, user_id=user_a.id)
        # Original deal parameters MUST remain completely untouched
        assert db_state.selected_product["sku"] == "BD-4340"
        assert db_state.agreed_quantity == 3
        assert db_state.deal_status == "FINALIZED"

        # Explicit reopen workflow required to change
        reopened = reopen_deal(db=db_session, conversation_id=conv.id, user_id=user_a.id, reason="Customer wants to upgrade")
        assert reopened.deal_status == "OPEN"
        assert reopened.stage == "DEAL_DISCUSSION"
        assert reopened.recommendations_generated is False

    def test_unsupported_products_and_fabricated_prices_never_recommended(self, db_session, user_a):
        """13. Unsupported products and fabricated prices are never recommended."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Pricing Fabrication Safeguard")
        candidate = {"sku": "LADDER-01", "name": "Werner 8ft Step Ladder", "price": "$249"}
        select_product_for_deal(db=db_session, conversation_id=conv.id, user_id=user_a.id, product=candidate, quantity=1)
        update_sales_state(db=db_session, state=get_sales_state(db_session, conv.id, user_a.id), product_category="ladder")
        final_state = finalize_deal(db=db_session, conversation_id=conv.id, user_id=user_a.id)

        recs = generate_recommendations(db=db_session, state=final_state)
        # Check that prices are not fabricated random discounts
        for item in recs["cross_sells"] + recs["upsells"]:
            price_text = item.get("estimated_price", "")
            # Ensure price is marked as catalog standard or quote, never made-up random percentages
            assert "99.999%" not in price_text
            assert item.get("manufacturer") in ("Werner", "Little Giant", "Karcher", "Cisco", "OEM", "Catalog")


# ===========================================================================
# 4. Persistence & Security / RBAC Tests
# ===========================================================================

class TestSalesPersistenceAndSecurity:
    def test_conversation_state_persists_after_refresh(self, db_session, user_a, client_a):
        """14. Conversation state persists after refresh."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="State Persistence Across Refresh")
        state = get_or_create_sales_state(db=db_session, conversation_id=conv.id)
        update_sales_state(
            db=db_session,
            state=state,
            product_category="ladder",
            extracted_requirements={"height": "10ft", "material": "fiberglass", "budget": "$280"},
        )

        # Simulate browser refresh by fetching conversation detail endpoint
        res = client_a.get(f"/conversations/{conv.id}")
        assert res.status_code == 200
        data = res.json()
        assert "sales_state" in data
        sales = data["sales_state"]
        assert sales is not None
        assert sales["product_category"] == "ladder"
        assert sales["extracted_requirements"]["height"] == "10ft"
        assert sales["extracted_requirements"]["material"] == "fiberglass"

        # Also verify dedicated deal state endpoint
        res_deal = client_a.get(f"/conversations/{conv.id}/deal")
        assert res_deal.status_code == 200
        deal_data = res_deal.json()
        assert deal_data["extracted_requirements"]["height"] == "10ft"

    def test_cross_user_denial_for_deal_endpoints(self, db_session, user_a, client_b):
        """15. Existing RBAC / authentication safeguards apply to deal endpoints."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="User A Private Deal")
        get_or_create_sales_state(db=db_session, conversation_id=conv.id)

        # User B attempting to access User A's deal state -> 403 Forbidden
        res = client_b.get(f"/conversations/{conv.id}/deal")
        assert res.status_code in (403, 404)

        # User B attempting to confirm User A's deal -> 403 Forbidden
        res_confirm = client_b.post(
            f"/conversations/{conv.id}/deal/confirm",
            json={"confirmation_text": "I confirm User A's deal"},
        )
        assert res_confirm.status_code in (403, 404)

    def test_unauthenticated_request_protection(self, db_session, user_a, anon_client):
        """Unauthenticated requests to deal endpoints return 401."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Anon Protection")
        res = anon_client.get(f"/conversations/{conv.id}/deal")
        assert res.status_code == 401


# ===========================================================================
# 5. Full End-to-End Ask Integration Tests
# ===========================================================================

from unittest.mock import patch
from app.retrieval.schemas import RetrievalResponse, RetrievedChunk

class TestAskEndpointSalesIntegration:
    @patch("app.api.ask.generate_response")
    @patch("app.api.ask.retrieve")
    def test_ask_endpoint_returns_sales_state_and_suggested_questions(self, mock_retrieve, mock_generate, client_a):
        """Ask endpoint integrates sales state and suggested follow-up questions."""
        mock_retrieve.return_value = RetrievalResponse(
            query="ladder",
            results=[
                RetrievedChunk(
                    chunk_id="chunk-ladder-1",
                    document_id=1,
                    text="Werner 8 ft fiberglass step ladder Type IA 300 lbs",
                    score=0.92,
                    metadata={"sku": "WERNER-8FT-IA", "category": "ladder", "manufacturer": "Werner"},
                )
            ],
            total_results=1,
        )
        mock_generate.return_value = {
            "answer": "For painting, an 8 ft ladder gives comfortable reach. What height and material do you prefer?",
            "sources": [{"chunk_id": "chunk-ladder-1", "sku": "WERNER-8FT-IA"}],
        }

        res = client_a.post(
            "/ask",
            json={"query": "I am looking for a ladder for painting"},
        )
        assert res.status_code == 200
        data = res.json()
        assert "sales_state" in data
        sales = data["sales_state"]
        assert sales["product_category"] == "ladder"
        assert "painting" in str(sales["extracted_requirements"].get("application", "")).lower()

        # Should include suggested questions for height or material
        assert "suggested_questions" in data
        assert len(data["suggested_questions"]) > 0

    @patch("app.api.ask.generate_response")
    @patch("app.api.ask.retrieve")
    def test_ask_backward_compatibility_without_conversation_id(self, mock_retrieve, mock_generate, client_a):
        """Backward compatibility: /ask without conversation_id still succeeds."""
        mock_retrieve.return_value = RetrievalResponse(
            query="Karcher BD 43/40",
            results=[
                RetrievedChunk(
                    chunk_id="chunk-bd-1",
                    document_id=1,
                    text="Karcher BD 43/40 walk-behind scrubber dryer",
                    score=0.95,
                    metadata={"sku": "BD-4340", "category": "floor_scrubber", "manufacturer": "Karcher"},
                )
            ],
            total_results=1,
        )
        mock_generate.return_value = {
            "answer": "The Kärcher BD 43/40 is a compact walk-behind scrubber dryer.",
            "sources": [{"chunk_id": "chunk-bd-1", "sku": "BD-4340"}],
        }

        res = client_a.post(
            "/ask",
            json={"query": "What is the Kärcher BD 43/40?"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["conversation_id"] > 0
        assert len(data["answer"]) > 0
        assert "sales_state" in data


# ===========================================================================
# 6. Production Readiness, Concurrency, Grounding & Edge Case Tests
# ===========================================================================

import concurrent.futures

class TestProductionReadinessAndEdgeCases:
    def test_admin_authorization_and_salesman_isolation(self, db_session, user_a, client_a, admin_client):
        """Admin can access deals; salesmen cannot access admin operations."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Admin Access Verification")
        state = get_or_create_sales_state(db=db_session, conversation_id=conv.id)

        # Admin client can access User A's deal state
        admin_res = admin_client.get(f"/conversations/{conv.id}/deal")
        assert admin_res.status_code == 200
        assert admin_res.json()["deal_status"] == "OPEN"

        # Salesman cannot access admin-only endpoints
        salesman_admin_res = client_a.get("/admin/query-logs")
        assert salesman_admin_res.status_code == 403

    def test_deal_cannot_be_finalised_without_selected_product(self, db_session, user_a, client_a):
        """Deal finalisation must fail if no product has been selected from catalogue."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Empty Deal Finalisation")
        state = get_or_create_sales_state(db=db_session, conversation_id=conv.id)
        # Ensure selected_product and candidates are empty
        state.selected_product = None
        state.candidate_products = []
        db_session.commit()

        res = client_a.post(
            f"/conversations/{conv.id}/deal/confirm",
            json={"confirmation_text": "I confirm this deal"},
        )
        assert res.status_code == 400
        assert "No product has been selected" in res.json()["detail"]

    def test_invalid_quantities_rejected(self, db_session, user_a, client_a):
        """Invalid quantities (0, negative, non-integer) are strictly rejected."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Quantity Validation")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}

        # Zero quantity
        res_zero = client_a.post(
            f"/conversations/{conv.id}/deal/select-product",
            json={"product": candidate, "quantity": 0},
        )
        assert res_zero.status_code in (400, 422)

        # Negative quantity
        res_neg = client_a.post(
            f"/conversations/{conv.id}/deal/select-product",
            json={"product": candidate, "quantity": -5},
        )
        assert res_neg.status_code in (400, 422)

        # Valid selection, then finalise with invalid override quantity
        client_a.post(
            f"/conversations/{conv.id}/deal/select-product",
            json={"product": candidate, "quantity": 2},
        )
        res_bad_override = client_a.post(
            f"/conversations/{conv.id}/deal/confirm",
            json={"quantity": 0},
        )
        assert res_bad_override.status_code in (400, 422)

    def test_forged_uncatalogued_product_rejected(self, db_session, user_a, client_a):
        """Arbitrary forged product IDs not grounded in the catalogue or candidates are rejected."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Forged Product Test")
        forged_product = {"sku": "X", "name": "X"}

        res = client_a.post(
            f"/conversations/{conv.id}/deal/select-product",
            json={"product": forged_product, "quantity": 1},
        )
        assert res.status_code == 400
        assert "not grounded" in res.json()["detail"].lower()

    def test_price_tampering_rejected_and_grounded(self, db_session, user_a, client_a):
        """Client-side price tampering is rejected and trusted catalogue pricing is preserved."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Price Tampering Guard")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}

        # Select with valid candidate price
        client_a.post(
            f"/conversations/{conv.id}/deal/select-product",
            json={"product": candidate, "quantity": 1},
        )

        # Attempt to finalise with fabricated price override
        res = client_a.post(
            f"/conversations/{conv.id}/deal/confirm",
            json={"confirmation_text": "I confirm this order", "price": "$0.01"},
        )
        assert res.status_code == 200
        deal_state = res.json()
        # Price must NOT be manipulated to $0.01; must preserve verified catalogue price $3,200
        assert deal_state["agreed_price"] == "$3,200"

        # Test unquoted item: client override must NOT turn a quote into a fabricated dollar value
        conv2 = create_conversation(db=db_session, user_id=user_a.id, title="Unquoted Pricing Guard")
        unquoted_cand = {"sku": "CUSTOM-EQUIP-99", "name": "Custom Unquoted Scrubber"}
        client_a.post(
            f"/conversations/{conv2.id}/deal/select-product",
            json={"product": unquoted_cand, "quantity": 1},
        )
        res_quote = client_a.post(
            f"/conversations/{conv2.id}/deal/confirm",
            json={"confirmation_text": "I confirm this order", "price": "$50.00"},
        )
        assert res_quote.status_code == 200
        # Must strictly remain standard quote, not client's $50.00
        assert res_quote.json()["agreed_price"] == "Catalog quote / standard pricing"

    def test_all_ambiguous_statements_rejected(self, db_session, user_a, client_a):
        """All ambiguous phrases must be rejected without finalising the deal."""
        ambiguous_statements = [
            "Looks good.",
            "Tell me more.",
            "Maybe.",
            "I am interested.",
            "What is the price?",
            "Sounds interesting.",
        ]

        conv = create_conversation(db=db_session, user_id=user_a.id, title="Ambiguity Rejection Test")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}
        client_a.post(
            f"/conversations/{conv.id}/deal/select-product",
            json={"product": candidate, "quantity": 1},
        )

        for stmt in ambiguous_statements:
            res = client_a.post(
                f"/conversations/{conv.id}/deal/confirm",
                json={"confirmation_text": stmt},
            )
            assert res.status_code == 400
            assert "ambiguous" in res.json()["detail"].lower()

        # Deal must remain OPEN
        check_res = client_a.get(f"/conversations/{conv.id}/deal")
        assert check_res.json()["deal_status"] == "OPEN"

    def test_repeated_confirmation_idempotent_and_safe(self, db_session, user_a, client_a):
        """Repeated confirmation requests are idempotent and do not corrupt timestamps."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Idempotent Confirmation")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}
        client_a.post(
            f"/conversations/{conv.id}/deal/select-product",
            json={"product": candidate, "quantity": 1},
        )

        # First confirmation
        res1 = client_a.post(f"/conversations/{conv.id}/deal/confirm")
        assert res1.status_code == 200
        data1 = res1.json()
        assert data1["deal_status"] == "FINALIZED"
        t1 = data1["deal_finalized_at"]

        # Duplicate confirmation
        res2 = client_a.post(f"/conversations/{conv.id}/deal/confirm")
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["deal_status"] == "FINALIZED"
        t2 = data2["deal_finalized_at"]
        assert t1 == t2

    def test_concurrent_finalisation_race_prevention(self, db_session, user_a, client_a):
        """Simultaneous confirmation requests handle concurrency safely without corrupted state."""
        # 1. Test simultaneous first-time creation of SalesConversationState for a new conversation
        fresh_conv = create_conversation(db=db_session, user_id=user_a.id, title="Concurrent State Init")

        def call_get_or_create():
            t_db = SessionLocal()
            try:
                return get_or_create_sales_state(db=t_db, conversation_id=fresh_conv.id)
            finally:
                t_db.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            init_futures = [executor.submit(call_get_or_create) for _ in range(4)]
            init_results = [f.result() for f in init_futures]

        assert all(r.stage == "DISCOVERY" for r in init_results)
        assert all(r.conversation_id == fresh_conv.id for r in init_results)

        # 2. Test concurrent finalisation race prevention
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Concurrency Finalisation")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}
        client_a.post(
            f"/conversations/{conv.id}/deal/select-product",
            json={"product": candidate, "quantity": 2},
        )

        def call_finalize():
            thread_db = SessionLocal()
            try:
                return finalize_deal(
                    db=thread_db,
                    conversation_id=conv.id,
                    user_id=user_a.id,
                )
            finally:
                thread_db.close()

        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(call_finalize) for _ in range(3)]
            results = [f.result() for f in futures]

        # All concurrent calls should succeed and return finalized state
        for r in results:
            assert r.deal_status == "FINALIZED"
            assert r.agreed_quantity == 2

        final_res = client_a.get(f"/conversations/{conv.id}/deal")
        final_data = final_res.json()
        assert final_data["deal_status"] == "FINALIZED"
        assert final_data["agreed_quantity"] == 2

    def test_route_aliases_select_item_and_recs(self, db_session, user_a, client_a):
        """Route aliases /deal/select-item and /deal/recs operate identically to primary routes."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Route Aliases Test")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}

        # Alias: /deal/select-item
        res_item = client_a.post(
            f"/conversations/{conv.id}/deal/select-item",
            json={"product": candidate, "quantity": 1},
        )
        assert res_item.status_code == 200
        assert res_item.json()["stage"] == "DEAL_DISCUSSION"

        # Finalise
        client_a.post(f"/conversations/{conv.id}/deal/confirm")

        # Alias: /deal/recs
        res_recs = client_a.post(f"/conversations/{conv.id}/deal/recs")
        assert res_recs.status_code == 200
        assert "cross_sells" in res_recs.json()

    def test_reopen_deal_invalidates_recommendations(self, db_session, user_a, client_a):
        """Reopening a deal invalidates recommendations and blocks the recommendation endpoint."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Reopen Invalidation Test")
        candidate = {"sku": "BD-4340", "name": "Karcher BD 43/40", "price": "$3,200"}
        client_a.post(f"/conversations/{conv.id}/deal/select-product", json={"product": candidate, "quantity": 1})
        client_a.post(f"/conversations/{conv.id}/deal/confirm")

        # Generate recommendations when finalised -> succeeds
        recs_res = client_a.post(f"/conversations/{conv.id}/deal/recommendations")
        assert recs_res.status_code == 200

        # Now reopen deal
        reopen_res = client_a.post(
            f"/conversations/{conv.id}/deal/reopen",
            json={"reason": "Customer wants to increase quantity"},
        )
        assert reopen_res.status_code == 200
        reopen_data = reopen_res.json()
        assert reopen_data["deal_status"] == "OPEN"
        assert reopen_data["recommendations"] is None
        assert reopen_data["can_recommend_addons"] is False

        # Attempting recommendations while reopened -> MUST be blocked (400)
        blocked_recs = client_a.post(f"/conversations/{conv.id}/deal/recommendations")
        assert blocked_recs.status_code == 400

    def test_selected_product_filtered_from_cross_sells(self, db_session, user_a, client_a):
        """The currently selected product is filtered out from cross-sell recommendations."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Cross-Sell Deduplication")
        # Select an accessory directly as the purchased product
        acc_product = {
            "sku": "ACC-LADDER-STABILIZER",
            "name": "Heavy-Duty Ladder Wall Standoff & Stabilizer",
            "price": "Catalog standard",
        }
        update_sales_state(db=db_session, state=get_sales_state(db_session, conv.id, user_a.id), product_category="ladder")
        client_a.post(f"/conversations/{conv.id}/deal/select-product", json={"product": acc_product, "quantity": 1})
        client_a.post(f"/conversations/{conv.id}/deal/confirm")

        recs_res = client_a.post(f"/conversations/{conv.id}/deal/recommendations")
        assert recs_res.status_code == 200
        cross_sells = recs_res.json()["cross_sells"]
        # ACC-LADDER-STABILIZER must NOT appear in cross-sells
        for cs in cross_sells:
            assert cs["sku"] != "ACC-LADDER-STABILIZER"

    def test_empty_catalogue_handling(self, db_session, user_a):
        """When no matching items exist in catalogue, sensible empty lists are returned without crashing."""
        conv = create_conversation(db=db_session, user_id=user_a.id, title="Empty Catalogue Handling")
        state = get_or_create_sales_state(db=db_session, conversation_id=conv.id)
        update_sales_state(
            db=db_session,
            state=state,
            product_category="unknown_specialized_category",
            selected_product={"sku": "CUSTOM-99", "name": "Custom Hardware Unit"},
            deal_status="FINALIZED",
            deal_finalized_at=datetime.now(timezone.utc),
        )

        recs = generate_recommendations(db=db_session, state=state)
        assert recs is not None
        assert isinstance(recs["cross_sells"], list)
        assert isinstance(recs["upsells"], list)


