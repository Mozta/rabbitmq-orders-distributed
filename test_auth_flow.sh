#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# Test de integración: flujo completo de autenticación
# Requiere: curl, jq, servicios levantados (docker compose up)
# Uso: ./test_auth_flow.sh [AUTH_URL] [GATEWAY_URL]
# ─────────────────────────────────────────────────────────────

set -euo pipefail

AUTH_URL="${1:-http://localhost:8001}"
GATEWAY_URL="${2:-http://localhost:8000}"
EMAIL="test_$(date +%s)@example.com"
PASSWORD="S3cur3P4ss!"

passed=0
failed=0

check() {
    local description="$1"
    local expected_code="$2"
    local actual_code="$3"

    if [ "$actual_code" -eq "$expected_code" ]; then
        echo "  ✅ $description (HTTP $actual_code)"
        ((passed++))
    else
        echo "  ❌ $description (esperado $expected_code, recibido $actual_code)"
        ((failed++))
    fi
}

echo "══════════════════════════════════════════════"
echo " Test de integración: Auth Flow"
echo " Auth:    $AUTH_URL"
echo " Gateway: $GATEWAY_URL"
echo " Email:   $EMAIL"
echo "══════════════════════════════════════════════"
echo ""

# ── 1. Health check ──────────────────────────────────────────
echo "1. Health checks"
code=$(curl -s -o /dev/null -w "%{http_code}" "$AUTH_URL/health")
check "Auth service health" 200 "$code"
echo ""

# ── 2. Signup ────────────────────────────────────────────────
echo "2. Signup"
response=$(curl -s -w "\n%{http_code}" -X POST "$AUTH_URL/auth/signup" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")
code=$(echo "$response" | tail -1)
body=$(echo "$response" | sed '$d')
check "Registro exitoso" 201 "$code"

USER_ID=$(echo "$body" | jq -r '.user_id')
echo "  → user_id: $USER_ID"

# Signup duplicado
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH_URL/auth/signup" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")
check "Signup duplicado rechazado" 409 "$code"
echo ""

# ── 3. Login ─────────────────────────────────────────────────
echo "3. Login"
response=$(curl -s -w "\n%{http_code}" -X POST "$AUTH_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$EMAIL\", \"password\": \"$PASSWORD\"}")
code=$(echo "$response" | tail -1)
body=$(echo "$response" | sed '$d')
check "Login exitoso" 200 "$code"

ACCESS_TOKEN=$(echo "$body" | jq -r '.access_token')
REFRESH_TOKEN=$(echo "$body" | jq -r '.refresh_token')
echo "  → access_token: ${ACCESS_TOKEN:0:20}..."
echo "  → refresh_token: ${REFRESH_TOKEN:0:20}..."

# Login con password incorrecto
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$EMAIL\", \"password\": \"wrongpass\"}")
check "Login con password incorrecto rechazado" 401 "$code"
echo ""

# ── 4. /auth/me ──────────────────────────────────────────────
echo "4. /auth/me"
response=$(curl -s -w "\n%{http_code}" "$AUTH_URL/auth/me" \
    -H "Authorization: Bearer $ACCESS_TOKEN")
code=$(echo "$response" | tail -1)
body=$(echo "$response" | sed '$d')
check "Me con token válido" 200 "$code"

ME_EMAIL=$(echo "$body" | jq -r '.email')
echo "  → email: $ME_EMAIL"

# Me sin token
code=$(curl -s -o /dev/null -w "%{http_code}" "$AUTH_URL/auth/me")
check "Me sin token rechazado" 403 "$code"
echo ""

# ── 5. Crear orden con auth ──────────────────────────────────
echo "5. Crear orden (gateway protegido)"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$GATEWAY_URL/orders" \
    -H "Content-Type: application/json" \
    -d '{"customer": "test", "items": [{"product": "Widget", "quantity": 1}]}')
check "Orden sin token rechazada" 401 "$code"

response=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY_URL/orders" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d '{"customer": "test", "items": [{"product": "Widget", "quantity": 1}]}')
code=$(echo "$response" | tail -1)
body=$(echo "$response" | sed '$d')
check "Orden con token válido aceptada" 202 "$code"

ORDER_ID=$(echo "$body" | jq -r '.order_id')
echo "  → order_id: $ORDER_ID"
echo ""

# ── 6. Refresh token ─────────────────────────────────────────
echo "6. Refresh token"
response=$(curl -s -w "\n%{http_code}" -X POST "$AUTH_URL/auth/refresh" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")
code=$(echo "$response" | tail -1)
body=$(echo "$response" | sed '$d')
check "Refresh exitoso" 200 "$code"

NEW_ACCESS=$(echo "$body" | jq -r '.access_token')
NEW_REFRESH=$(echo "$body" | jq -r '.refresh_token')
echo "  → nuevo access_token: ${NEW_ACCESS:0:20}..."

# Reuso del refresh token anterior (debe fallar por rotación)
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH_URL/auth/refresh" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}")
check "Reuso de refresh token revocado rechazado" 401 "$code"
echo ""

# ── 7. Logout ────────────────────────────────────────────────
echo "7. Logout"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH_URL/auth/logout" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\": \"$NEW_REFRESH\"}")
check "Logout exitoso" 204 "$code"

# Refresh después de logout
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH_URL/auth/refresh" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\": \"$NEW_REFRESH\"}")
check "Refresh tras logout rechazado" 401 "$code"
echo ""

# ── 8. JWKS ──────────────────────────────────────────────────
echo "8. JWKS endpoint"
response=$(curl -s -w "\n%{http_code}" "$AUTH_URL/auth/.well-known/jwks.json")
code=$(echo "$response" | tail -1)
body=$(echo "$response" | sed '$d')
check "JWKS accesible" 200 "$code"

KEY_TYPE=$(echo "$body" | jq -r '.keys[0].kty')
echo "  → kty: $KEY_TYPE, alg: $(echo "$body" | jq -r '.keys[0].alg')"
echo ""

# ── Resumen ──────────────────────────────────────────────────
echo "══════════════════════════════════════════════"
echo " Resultados: $passed passed, $failed failed"
echo "══════════════════════════════════════════════"

[ "$failed" -eq 0 ] && exit 0 || exit 1
