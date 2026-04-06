package identity

import (
	"crypto/ed25519"
	"crypto/rand"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"

	"golang.org/x/crypto/cryptobyte"
	"golang.org/x/crypto/cryptobyte/asn1"
)

// GenerateKeypair generates a new Ed25519 keypair.
// Returns (privateKeyPEM, publicKeyJWK, privateKey, error)
func GenerateKeypair() ([]byte, []byte, ed25519.PrivateKey, error) {
	pub, priv, err := ed25519.GenerateKey(rand.Reader)
	if err != nil {
		return nil, nil, nil, err
	}

	pemBytes, err := marshalPrivateKeyPEM(priv)
	if err != nil {
		return nil, nil, nil, err
	}

	jwk := map[string]string{
		"kty": "OKP",
		"crv": "Ed25519",
		"x":   b64url(pub),
	}
	jwkBytes, err := json.Marshal(jwk)
	if err != nil {
		return nil, nil, nil, err
	}

	return pemBytes, jwkBytes, priv, nil
}

// LoadPrivateKey loads an Ed25519 private key from PEM bytes
func LoadPrivateKey(pemBytes []byte) (ed25519.PrivateKey, error) {
	block, _ := pem.Decode(pemBytes)
	if block == nil {
		return nil, nil
	}
	// Parse PKCS8 DER
	return parseEd25519PKCS8(block.Bytes)
}

func marshalPrivateKeyPEM(priv ed25519.PrivateKey) ([]byte, error) {
	der, err := marshalEd25519PKCS8(priv)
	if err != nil {
		return nil, err
	}
	block := &pem.Block{Type: "PRIVATE KEY", Bytes: der}
	return pem.EncodeToMemory(block), nil
}

// marshalEd25519PKCS8 encodes an Ed25519 private key as PKCS#8 DER
func marshalEd25519PKCS8(priv ed25519.PrivateKey) ([]byte, error) {
	// PKCS8: SEQUENCE { INTEGER 0, SEQUENCE { OID 1.3.101.112 }, OCTET STRING { OCTET STRING { seed } } }
	seed := priv.Seed()
	var b cryptobyte.Builder
	b.AddASN1(asn1.SEQUENCE, func(b *cryptobyte.Builder) {
		b.AddASN1Int64(0) // version
		b.AddASN1(asn1.SEQUENCE, func(b *cryptobyte.Builder) {
			// OID for Ed25519: 1.3.101.112
			b.AddBytes([]byte{0x06, 0x03, 0x2b, 0x65, 0x70})
		})
		b.AddASN1OctetString(func() []byte {
			var inner cryptobyte.Builder
			inner.AddASN1OctetString(seed)
			out, _ := inner.Bytes()
			return out
		}())
	})
	return b.Bytes()
}

// parseEd25519PKCS8 decodes PKCS#8 DER to Ed25519 private key
func parseEd25519PKCS8(der []byte) (ed25519.PrivateKey, error) {
	input := cryptobyte.String(der)
	var inner cryptobyte.String
	if !input.ReadASN1(&inner, asn1.SEQUENCE) {
		return nil, nil
	}
	// skip version
	var version int64
	if !inner.ReadASN1Int64WithTag(&version, asn1.INTEGER) {
		return nil, nil
	}
	// skip algorithm identifier
	var alg cryptobyte.String
	if !inner.ReadASN1(&alg, asn1.SEQUENCE) {
		return nil, nil
	}
	// read private key octet string
	var privOuter cryptobyte.String
	if !inner.ReadASN1(&privOuter, asn1.OCTET_STRING) {
		return nil, nil
	}
	var seed cryptobyte.String
	if !privOuter.ReadASN1(&seed, asn1.OCTET_STRING) {
		return nil, nil
	}
	return ed25519.NewKeyFromSeed([]byte(seed)), nil
}

func b64url(data []byte) string {
	return base64.RawURLEncoding.EncodeToString(data)
}
