# Rolea Topup (UI/UX & Full-Stack Platform)

A high-fidelity, fully interactive website for **Rolea Topup** focusing on **Roblox Robux Send**, featuring responsive mobile-app and desktop layouts, Roblox username verification, ABA KHQR payment generation with dynamic countdown, real-time order polling, automated delivery simulation, browser-persisted "My Orders" tracking, and an **Admin Console**.

---

## 🚀 Quick Start

### 1. Requirements
- Node.js (v18+)

### 2. Run the Web Server
```bash
# Navigate to project folder
cd C:\Users\PC\.gemini\antigravity\scratch\yuki-topup

# Start server
node server.js
```

### 3. Open in Browser
- **Homepage (Storefront)**: [http://localhost:3000](http://localhost:3000)
- **Roblox Robux Send**: [http://localhost:3000/game/roblox](http://localhost:3000/game/roblox)
- **Check Order / My Orders**: [http://localhost:3000/check-order](http://localhost:3000/check-order)
- **Admin Panel**: [http://localhost:3000/admin](http://localhost:3000/admin) *(Username: `admin`, Password: `admin123`)*

---

## ✨ Features & Architecture

### 1. Authentic UI / UX Design
- **Branding**: Official transparent "Rolea" circular badge logo with ribbon, characters, and cute styling.
- **Dual Display Modes**:
  - **Mobile (Phone view)**: Top header with Telegram action button, banner carousel, product card, bottom fixed navigation (`Home`, `Games`, `Orders`), and floating support FAB.
  - **Desktop view**: Sticky header (`.desktop-nav`), scroll blur/shadow transitions, live search bar, and multi-pane layout.
- **Typography & Aesthetics**: Oxanium & Noto Sans Khmer fonts, royal blue/violet glowing accents (`#2066ed`, `#63b7ff`), crisp cards, and responsive micro-interactions.

### 2. Roblox Robux Topup Flow
- **Step 1: Enter your account**: Live username checker that queries the official Roblox User API to fetch avatar headshots and display names.
- **Step 2: Choose a top-up**: 50, 100, 200, 300, 400, 500, 1000, 2000 Robux cards with dynamic price summary.
- **Step 3: ABA KHQR Payment**: Payment selection with ABA logo.
- **Live KHQR Modal**:
  - Left pane: Standard Bakong EMVCo KHQR code generated via `qrcode`, 5:00 countdown timer, scan status.
  - Right pane: Roblox avatar, display name, handle, Robux quantity, Order ID, and status notes.
  - **Test Simulator Controls**: Direct test buttons (`📲 Scan QR`, `💳 Pay Now`, `⚡ Deliver`) allowing you to simulate the entire buyer lifecycle without Cambodian bank apps!

### 3. Order Tracking & "My Orders" Dashboard
- Uses `PutiOrders` in `localStorage` to auto-restore orders made on that device.
- Filter by status: `All`, `Unpaid`, `Paid`, `Sent`, `On hold`, `Failed`.
- Full order details card with player avatar, timestamp, delivery status, and "Copy Order ID" / "Continue payment" / "View receipt" buttons.
- Secure lookup form by Order ID, Roblox username, and private receipt token.

### 4. Admin Management Console
- Protected sign in at `/admin/login`.
- **Overview**: Real-time sales revenue, completed order counter, total Robux delivered.
- **Orders Queue**: Live table with buyer avatars, status badges, and 1-click fulfillment actions (`Pay`, `Send`, `Hold`, `Delete`).
- **Robux Plans Manager**: Add new custom Robux pricing tiers dynamically saved to `packages.json`.
- **Store Settings**: Customize Telegram handle, KHQR merchant account, and auto-fulfillment behavior.
