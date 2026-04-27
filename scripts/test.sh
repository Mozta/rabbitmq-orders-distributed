#!/usr/bin/env bash
# Integration tests for CI — requires all services running via docker compose
set -euo pipefail

GATEWAY_URL="${GATEWAY_URL:-http://localhost:8000}"
AUTH_URL="${AUTH_URL:-http://localhost:8001}"
EMAIL="ci_$(date +%s)@test.com"
PASSWORD="C1P4ss!Test"

passed=0
failed=0

check() {
    local desc="$1" expected="$2" actual="$3"
    if [ "$actual" -eq "$expected" ]; then
        echo "  PASS  $desc (HTTP $actual)"
        passed=$((passed + 1))
    else
        echo "  FAIL  $desc (expected $expected, got $actual)"
        failed=$((failed + 1))
    fi
}

echo "======================================================"
echo " CI Integration Tests"
echo " Gateway: $GATEWAY_URL"
echo " Auth:    $AUTH_URL"
echo "======================================================"
echo ""

# ── 1. Health checks ──────────────────────────────────────────
echo "1. Health checks"
check "api-gateway /health" 200 "$(curl -s -o /dev/null -w "%{http_code}" "$GATEWAY_URL/health")"
check "auth-service /health" 200 "$(curl -s -o /dev/null -w "%{http_code}" "$AUTH_URL/health")"
echo ""

# ── 2. JWKS accesible ────────────────────────────────────────
echo "2. JWKS"
JWKS=$(curl -s "$AUTH_URL/auth/.well-known/jwks.json")
JWKS_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$AUTH_URL/auth/.well-known/jwks.json")
check "JWKS endpoint accesible" 200 "$JWKS_CODE"
echo "  -> kty: $(echo "$JWKS" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['keys'][0]['kty'])")"
echo ""

# ── 3. Signup ────────────────────────────────────────────────
echo "3. Signup"
SIGNUP=$(curl -s -w "\n%{http_code}" -X POST "$AUTH_URL/auth/signup" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
check "Registro nuevo usuario" 201 "$(echo "$SIGNUP" | tail -1)"

check "Signup duplicado rechazado" 409 "$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH_URL/auth/signup" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")"
echo ""

# ── 4. Login ─────────────────────────────────────────────────
echo "4. Login"
LOGIN=$(curl -s -w "\n%{http_code}" -X POST "$AUTH_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
LOGIN_CODE=$(echo "$LOGIN" | tail -1)
LOGIN_BODY=$(echo "$LOGIN" | sed '$d')
check "Login exitoso" 200 "$LOGIN_CODE"

ACCESS_TOKEN=$(echo "$LOGIN_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
REFRESH_TOKEN=$(echo "$LOGIN_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")
echo "  -> access_token: ${ACCESS_TOKEN:0:20}..."

check "Login con password incorrecto rechazado" 401 "$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"$EMAIL\",\"password\":\"wrong\"}")"
echo ""

# ── 5. Crear orden (gateway protegido) ───────────────────────
echo "5. Ordenes"
check "Orden sin token rechazada" 401 "$(curl -s -o /dev/null -w "%{http_code}" -X POST "$GATEWAY_URL/orders" \
    -H "Content-Type: application/json" \
    -d '{"customer":"ci","items":[{"sku":"WIDGET-001","qty":1}]}')"

ORDER=$(curl -s -w "\n%{http_code}" -X POST "$GATEWAY_URL/orders" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d '{"customer":"ci","items":[{"sku":"WIDGET-001","qty":1}]}')
ORDER_CODE=$(echo "$ORDER" | tail -1)
ORDER_BODY=$(echo "$ORDER" | sed '$d')
check "Orden con token válido aceptada" 202 "$ORDER_CODE"
echo "  -> order_id: $(echo "$ORDER_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('order_id','n/a'))")"
echo ""

# ── 6. Refresh token ─────────────────────────────────────────
echo "6. Refresh token"
REFRESH=$(curl -s -w "\n%{http_code}" -X POST "$AUTH_URL/auth/refresh" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}")
REFRESH_CODE=$(echo "$REFRESH" | tail -1)
REFRESH_BODY=$(echo "$REFRESH" | sed '$d')
check "Refresh exitoso" 200 "$REFRESH_CODE"

NEW_REFRESH=$(echo "$REFRESH_BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['refresh_token'])")

check "Reuso de refresh token revocado rechazado" 401 "$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH_URL/auth/refresh" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\":\"$REFRESH_TOKEN\"}")"
echo ""

# ── 7. Logout ────────────────────────────────────────────────
echo "7. Logout"
check "Logout exitoso" 204 "$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH_URL/auth/logout" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\":\"$NEW_REFRESH\"}")"

check "Refresh tras logout rechazado" 401 "$(curl -s -o /dev/null -w "%{http_code}" -X POST "$AUTH_URL/auth/refresh" \
    -H "Content-Type: application/json" \
    -d "{\"refresh_token\":\"$NEW_REFRESH\"}")"
echo ""

# ── Resumen ───────────────────────────────────────────────────
echo "======================================================"
echo " Resultados: $passed passed, $failed failed"
echo "======================================================"

[ "$failed" -eq 0 ] && exit 0 || exit 1
