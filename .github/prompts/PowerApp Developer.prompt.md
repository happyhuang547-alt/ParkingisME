---
name: PowerApp Developer
description: Describe when to use this prompt
---

<!-- Tip: Use /create-prompt in chat to generate content with agent assistance -->

# Role

You are a Senior Microsoft Power Platform UX Designer, Power Apps Solution Architect, and Enterprise Product Designer.

Your task is to design a modern Microsoft Power Apps Canvas Application that serves as an Enterprise Application Catalog Portal.

The application should follow Microsoft Fluent UI design principles and look similar to the Microsoft Power Platform Admin Center, Azure Portal dashboard, and Microsoft 365 Admin Center.

---

# Goal

Design a Power Apps Canvas App called:

**PowerApps 分類清單**

Purpose:

Provide a centralized application catalog where users can browse, search, filter, and launch available Power Apps across the organization.

The design must be production-ready, enterprise-grade, modern, responsive, and optimized for Power Apps Canvas App implementation.

---

# Design Language

Use:

* Microsoft Fluent UI
* Power Platform Design System
* Azure Portal Style Cards
* Microsoft 365 Admin Center Experience

Visual Style:

* Clean
* Minimalist
* Enterprise
* Modern
* Professional

Color Palette:

Background:
#F3F6FA

Primary:
#4F78C4

Primary Hover:
#3D68B8

Text Primary:
#1F2937

Text Secondary:
#6B7280

Border:
#E5E7EB

Success:
#22C55E

Warning:
#F59E0B

Error:
#EF4444

White:
#FFFFFF

---

# Typography

Font Family:

Segoe UI

Title:
32px
Bold

Section Heading:
20px
SemiBold

Card Title:
18px
Bold

Body:
14px

Metadata:
12px

---

# Layout Structure

Create a responsive Power Apps Canvas App page.

Desktop Width:
1440px

Tablet Width:
1024px

Mobile Width:
390px

Spacing System:

8px Grid

Card Radius:

16px

Shadow:

0px 4px 16px rgba(0,0,0,0.08)

---

# Page Layout

## Header Section

Top padding: 32px

Display:

Small Label:

POWER APPS PORTAL

Style:
Uppercase
12px
Blue

Main Title:

PowerApps 分類清單

Style:
32px
Bold

Subtitle:

列出可存取的 PowerApps，支援分類與點擊開啟。

Style:
14px
Gray

---

## Toolbar Section

Create a sticky toolbar.

Height:
72px

Background:
White

Radius:
16px

Shadow:
Light

### Left Area

Category Pills

Style:

Rounded pill buttons

Selected:

Blue background
White text

Unselected:

White background
Gray border

Categories:

全部 (3)

EHS (2)

IT_TEST (1)

Hover State:

Soft blue tint

Animation:
150ms ease

---

### Right Area

Language Dropdown

Label:

語言

Default:

zh-TW

Style:

Fluent UI Dropdown

---

Search Box

Placeholder:

搜尋名稱、擁有者、描述...

Icon:

Search

Width:

320px

Behavior:

Real-time filtering

---

# Application Gallery

Display applications in a responsive card grid.

Desktop:

4 columns

Tablet:

2 columns

Mobile:

1 column

Gap:

24px

---

# Application Card Design

Card Style:

Background:
White

Radius:
16px

Shadow:
Soft

Padding:
20px

Hover:

TranslateY(-4px)

Increase Shadow

Transition:
200ms ease

---

# Card Header

Top Left:

Category Badge

Example:

其他

Style:

Pill Badge

Blue Tint Background

Blue Text

---

Top Right:

Data Source Label

Example:

CL_AppLists

Style:

12px
Gray

---

# Application Information

App Name

Example:

IT_ASSET_MANAGEMENT

Style:

18px
Bold

Dark Text

---

Description

Example:

企業資產管理系統，提供資產申請、追蹤、盤點與報表功能。

Style:

14px

Maximum:
2 lines

Ellipsis Overflow

---

# Metadata Section

Display in two-column layout.

Row 1

Label:
擁有者

Value:
Jemmy Chang

---

Row 2

Label:
最後更新

Value:
2026/06/10

---

# Action Button

Full Width

Height:
44px

Background:
#4F78C4

Text:
White

Label:

開啟 App

Radius:
12px

Hover:

Dark Blue

Cursor:
Pointer

Click Action:

Launch Power App URL

---

# Search Experience

Search should filter:

* App Name
* Description
* Owner
* Category

Results update instantly.

No search button required.

---

# Category Experience

When category changes:

* Update gallery
* Update result count
* Smooth animation

Examples:

全部 (12)

EHS (5)

IT_TEST (4)

HR (3)

Finance (2)

---

# Empty State

If no result found:

Icon:
Search

Message:

找不到符合條件的應用程式

Subtext:

請調整搜尋條件或選擇其他分類

---

# Loading State

Use Fluent UI Skeleton Loaders.

Show:

* Card placeholders
* Animated shimmer effect

---

# Accessibility

Must support:

* Keyboard navigation
* Screen readers
* WCAG AA
* High contrast mode

---

# Power Apps Components

Use Power Apps Canvas App controls:

* Horizontal Container
* Vertical Container
* Flexible Height Gallery
* Modern Button
* Modern Text Input
* Modern Dropdown
* Modern Badge
* Modern Icon
* Responsive Layout Containers

---

# Data Source

SharePoint List:

CL_AppLists

Columns:

Title

Description

Category

Owner

LastModified

AppURL

Environment

Status

---

# Example Record

{
"Title": "IT_ASSET_MANAGEMENT",
"Description": "企業資產管理系統",
"Category": "IT_TEST",
"Owner": "Jemmy Chang",
"LastModified": "2026/06/10",
"AppURL": "https://apps.powerapps.com/...",
"Environment": "Production",
"Status": "Active"
}

---

# Deliverables

Generate:

1. High-fidelity Figma UI Design
2. Power Apps Canvas App Layout
3. Responsive Desktop / Tablet / Mobile Views
4. Fluent UI Component Specifications
5. Power Apps Control Mapping
6. Color & Typography Guide
7. Production-ready Enterprise Dashboard
8. Modern Microsoft-style Application Catalog Experience

The final design should look like a combination of:

* Microsoft Power Platform Admin Center
* Azure Portal Dashboard
* Microsoft 365 Admin Center
* Enterprise Application Marketplace
