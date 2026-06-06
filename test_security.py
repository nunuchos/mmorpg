from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token

# Passwords
hashed = hash_password("Secret1234")
print(hashed)
# $2b$12$... (different every time because of random salt)

print(verify_password("Secret1234", hashed))   # True
print(verify_password("wrongpassword", hashed)) # False

# Access token
token = create_access_token("player-uuid-here")
print(token)
# eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

payload = decode_token(token)
print(payload)
# {'sub': 'player-uuid-here', 'type': 'access', 'exp': 1234567890}

# Refresh token — same player ID, different type
refresh = create_refresh_token("player-uuid-here")
refresh_payload = decode_token(refresh)
print(refresh_payload["type"])  # 'refresh'

# Verify type guard works
print(payload["type"])         # 'access'
print(refresh_payload["type"]) # 'refresh'