# TapPay

**A Tap button for payment apps, guarded by AI.**

TapPay adds a "Tap" option next to "Scan QR" inside a payment app. The customer taps their phone on the shop's NFC tag, sees the verified shop name, enters the amount, and pays. An AI check looks at the payment before it is sent, and a speaker at the shop announces the amount when the money arrives.

Built for the PayPal AI Hackathon. Payments use the PayPal sandbox, so no real money moves.

## Try it

- Customer app: https://adeshsasikumar7-ai.github.io/tappay-test/
- Shopkeeper speaker page: https://adeshsasikumar7-ai.github.io/tappay-test/shopkeeper.html

**Without NFC:** on the customer app, press "Try without NFC (demo)", enter an amount, and pay. On the shopkeeper page, press "Start listening", then "Simulate a payment (demo)" to hear the announcement.

**With NFC:** use an Android phone with NFC and Chrome. Write the text `shop_001` to an NTAG213 tag, open the customer app, press Tap, and hold the phone to the tag. A tag with any other ID shows an "Unknown tag" warning.

## How it works

1. The shopkeeper says the total aloud, as shops do today.
2. The customer taps the shop's NFC tag. The tag holds only a shop ID, never an amount.
3. The app looks up the shop and shows its verified name.
4. The customer enters the amount and approves the payment through PayPal.
5. The shop's speaker announces "amount received". If a fake tag has been stuck over the real one, the money never reaches the shop and the speaker stays silent.

Phones without NFC use the Scan QR fallback.

## Status

- Done: customer app (tap, QR fallback, pay and success screens), shopkeeper speaker page, unknown-tag warning.
- In progress: PayPal sandbox payments and the AI payment check (server).
- Demo data: the contacts, activity list, and account screens use sample data.

## Built with

- HTML, CSS, and JavaScript
- Web NFC (Chrome on Android) and the browser's speech synthesis
- GitHub Pages for hosting
- PayPal sandbox
- AI tools: [to be filled in by the team]

## Team

- Adesh (app, NFC, shopkeeper page, demo)
- Aadarssh,Akshaj (backend, PayPal, AI)

## License

MIT. See the LICENSE file.
