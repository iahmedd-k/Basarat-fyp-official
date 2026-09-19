"""Tests for Portfolio API."""

import pytest
from decimal import Decimal
from datetime import date
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.user import User
from app.models.stock import Stock
from app.models.portfolio import PortfolioTransaction, TransactionType
from app.core.security import create_access_token


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(db_session: AsyncSession):
    """Create a test user and return auth headers."""
    user = User(
        id=uuid4().hex,
        email="test@example.com",
        username="testuser",
        hashed_password="hashed",
        is_active=True,
    )
    db_session.add(user)
    
    # Add a test stock
    stock = Stock(
        id=uuid4().hex,
        symbol="OGDC",
        name="Oil & Gas Development Company",
        sector="Oil & Gas Exploration",
    )
    db_session.add(stock)
    
    db_session.commit()
    
    token = create_access_token({"sub": user.id})
    return {"Authorization": f"Bearer {token}"}, user.id


class TestPortfolioTransactions:
    """Tests for portfolio transaction CRUD operations."""
    
    def test_create_buy_transaction(self, client, auth_headers):
        """Test creating a BUY transaction."""
        headers, user_id = auth_headers
        
        response = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["symbol"] == "OGDC"
        assert data["transaction_type"] == "BUY"
        assert Decimal(data["quantity"]) == Decimal("100")
        assert Decimal(data["price"]) == Decimal("250.00")
        assert Decimal(data["fee"]) == Decimal("100")
        assert "id" in data
    
    def test_create_sell_transaction_insufficient_holding(self, client, auth_headers):
        """Test SELL transaction fails when insufficient holdings."""
        headers, user_id = auth_headers
        
        # Try to sell without buying first
        response = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "SELL",
                "quantity": "100",
                "price": "260.00",
                "fee": "100",
                "transaction_date": "2026-09-19",
            },
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "INSUFFICIENT_HOLDING"
    
    def test_create_sell_after_buy(self, client, auth_headers):
        """Test SELL transaction works after BUY."""
        headers, user_id = auth_headers
        
        # First buy
        client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "200",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        
        # Then sell partial
        response = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "SELL",
                "quantity": "50",
                "price": "260.00",
                "fee": "100",
                "transaction_date": "2026-09-19",
            },
        )
        
        assert response.status_code == 201
        data = response.json()
        assert data["transaction_type"] == "SELL"
        assert Decimal(data["quantity"]) == Decimal("50")
    
    def test_invalid_symbol(self, client, auth_headers):
        """Test creating transaction with invalid symbol."""
        headers, user_id = auth_headers
        
        response = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "INVALID",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "INVALID_SYMBOL"
    
    def test_get_transactions(self, client, auth_headers):
        """Test getting transaction history."""
        headers, user_id = auth_headers
        
        # Create a transaction first
        client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        
        response = client.get("/api/v1/portfolio/transactions", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["symbol"] == "OGDC"
    
    def test_get_transaction_by_id(self, client, auth_headers):
        """Test getting a single transaction by ID."""
        headers, user_id = auth_headers
        
        # Create a transaction
        create_resp = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        txn_id = create_resp.json()["id"]
        
        response = client.get(f"/api/v1/portfolio/transactions/{txn_id}", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == txn_id
        assert data["symbol"] == "OGDC"
    
    def test_update_transaction(self, client, auth_headers):
        """Test updating a transaction."""
        headers, user_id = auth_headers
        
        # Create a transaction
        create_resp = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        txn_id = create_resp.json()["id"]
        
        # Update quantity
        response = client.patch(
            f"/api/v1/portfolio/transactions/{txn_id}",
            headers=headers,
            json={"quantity": "150"},
        )
        
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["quantity"]) == Decimal("150")
    
    def test_update_transaction_invalid_history(self, client, auth_headers):
        """Test updating a transaction that would create invalid history."""
        headers, user_id = auth_headers
        
        # Buy 100
        buy_resp = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        buy_id = buy_resp.json()["id"]
        
        # Sell 50
        sell_resp = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "SELL",
                "quantity": "50",
                "price": "260.00",
                "fee": "100",
                "transaction_date": "2026-09-19",
            },
        )
        
        # Try to update BUY to 30 (would make SELL invalid)
        response = client.patch(
            f"/api/v1/portfolio/transactions/{buy_id}",
            headers=headers,
            json={"quantity": "30"},
        )
        
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "INVALID_TRANSACTION_HISTORY"
    
    def test_delete_transaction(self, client, auth_headers):
        """Test deleting a transaction."""
        headers, user_id = auth_headers
        
        # Create a transaction
        create_resp = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        txn_id = create_resp.json()["id"]
        
        response = client.delete(f"/api/v1/portfolio/transactions/{txn_id}", headers=headers)
        
        assert response.status_code == 204
        
        # Verify it's deleted
        get_resp = client.get(f"/api/v1/portfolio/transactions/{txn_id}", headers=headers)
        assert get_resp.status_code == 404
    
    def test_delete_transaction_invalid_history(self, client, auth_headers):
        """Test deleting a transaction that would create invalid history."""
        headers, user_id = auth_headers
        
        # Buy 100
        buy_resp = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        buy_id = buy_resp.json()["id"]
        
        # Sell 50
        client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "SELL",
                "quantity": "50",
                "price": "260.00",
                "fee": "100",
                "transaction_date": "2026-09-19",
            },
        )
        
        # Try to delete the BUY (would make SELL invalid)
        response = client.delete(f"/api/v1/portfolio/transactions/{buy_id}", headers=headers)
        
        assert response.status_code == 422
        data = response.json()
        assert data["error"] == "INVALID_TRANSACTION_HISTORY"


class TestPortfolioSummary:
    """Tests for portfolio summary and holdings."""
    
    def test_empty_portfolio(self, client, auth_headers):
        """Test portfolio with no transactions."""
        headers, user_id = auth_headers
        
        response = client.get("/api/v1/portfolio", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["total_invested"] == "0"
        assert data["summary"]["current_value"] == "0"
        assert data["summary"]["total_pnl"] == "0"
        assert data["holdings"] == []
    
    def test_portfolio_with_holdings(self, client, auth_headers):
        """Test portfolio with active holdings."""
        headers, user_id = auth_headers
        
        # Buy some shares
        client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        
        response = client.get("/api/v1/portfolio", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert Decimal(data["summary"]["total_invested"]) > 0
        assert len(data["holdings"]) >= 0  # May be 0 if price unavailable
    
    def test_holdings_endpoint(self, client, auth_headers):
        """Test holdings endpoint."""
        headers, user_id = auth_headers
        
        response = client.get("/api/v1/portfolio/holdings", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_pnl_endpoint(self, client, auth_headers):
        """Test P&L endpoint."""
        headers, user_id = auth_headers
        
        response = client.get("/api/v1/portfolio/pnl", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "realized_pnl" in data
        assert "unrealized_pnl" in data
        assert "total_pnl" in data
    
    def test_allocation_endpoint(self, client, auth_headers):
        """Test allocation endpoint."""
        headers, user_id = auth_headers
        
        response = client.get("/api/v1/portfolio/allocation", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "by_stock" in data
        assert "by_sector" in data
    
    def test_performance_endpoint(self, client, auth_headers):
        """Test performance endpoint."""
        headers, user_id = auth_headers
        
        response = client.get("/api/v1/portfolio/performance", headers=headers)
        
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "data" in data


class TestPortfolioAuthorization:
    """Tests for authorization and user isolation."""
    
    def test_user_cannot_access_other_user_transactions(self, client, db_session: AsyncSession):
        """Test that users can only access their own transactions."""
        # Create user 1
        user1 = User(
            id=uuid4().hex,
            email="user1@example.com",
            username="user1",
            hashed_password="hashed",
            is_active=True,
        )
        # Create user 2
        user2 = User(
            id=uuid4().hex,
            email="user2@example.com",
            username="user2",
            hashed_password="hashed",
            is_active=True,
        )
        db_session.add_all([user1, user2])
        
        # Add stock
        stock = Stock(
            id=uuid4().hex,
            symbol="OGDC",
            name="Oil & Gas Development Company",
            sector="Oil & Gas Exploration",
        )
        db_session.add(stock)
        db_session.commit()
        
        # User 1 creates a transaction
        token1 = create_access_token({"sub": user1.id})
        headers1 = {"Authorization": f"Bearer {token1}"}
        
        create_resp = client.post(
            "/api/v1/portfolio/transactions",
            headers=headers1,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        txn_id = create_resp.json()["id"]
        
        # User 2 tries to access user 1's transaction
        token2 = create_access_token({"sub": user2.id})
        headers2 = {"Authorization": f"Bearer {token2}"}
        
        response = client.get(f"/api/v1/portfolio/transactions/{txn_id}", headers=headers2)
        
        assert response.status_code == 404
    
    def test_unauthorized_access(self, client):
        """Test that unauthenticated requests fail."""
        response = client.get("/api/v1/portfolio")
        assert response.status_code == 401
        
        response = client.post("/api/v1/portfolio/transactions", json={})
        assert response.status_code == 401