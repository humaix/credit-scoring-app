## Qoder AI Coding Hands-on Lab – Building and Evolving an AI-Generated Order System

### Lab Guide & Demo Script

---

### 1. Lab Overview

Welcome to the Qoder AI Coding Hands-on Lab. In this workshop, you will experience firsthand how AI coding tools can accelerate every phase of software development — from initial code generation and feature evolution to architecture review, code quality analysis, microservice refactoring, and CI/CD integration.

You will build a Spring Boot order management system from scratch using AI, then progressively enhance and transform it through a series of realistic development stages. Each stage mirrors the kind of work enterprise developers do every day, but with AI as a powerful collaborator.

This guide serves two audiences. If you are a **hands-on participant**, follow the step-by-step instructions and prompts. If you are an **instructor or demo presenter**, refer to the Instructor Notes sections (marked with 🎤) embedded throughout, as well as the consolidated notes in Section 13.

**Estimated Duration:** 2.5 – 3 hours (can be shortened to a 60-minute demo by selecting specific stages)

---

### 2. Business Scenario

You are a developer at a mid-sized e-commerce company. The product team has requested a new internal **Order Pricing Tool** that allows sales staff to quickly calculate order totals. The tool must account for unit pricing, quantity, discount codes, VIP customer tiers, tax, and shipping fees.

Your team has decided to use AI-assisted development to accelerate delivery. Over the course of this lab, you will:

1. Generate a working order system with a modern UI
2. Add a new feature (Order Remark)
3. Have AI explain the system architecture to a new team member
4. Run an AI-powered code review
5. Refactor the monolith into microservices
6. Explore how AI code review integrates into CI/CD pipelines

---

### 3. Learning Objectives

By the end of this lab, you will be able to:

- Use AI to generate a complete, runnable Spring Boot application with a modern frontend
- Modify an existing codebase by describing desired changes to an AI assistant
- Leverage AI to produce architectural explanations and onboarding documentation
- Conduct AI-assisted code reviews that catch real-world issues like missing validation and precision errors
- Refactor a monolithic application into microservices with AI guidance
- Understand how AI code review tools integrate into CI/CD pipelines for automated quality gates

---

### 4. Environment Setup

#### Prerequisites

Before starting the lab, ensure you have the following installed on your machine:

| Tool | Version | Purpose |
|------|---------|---------|
| JDK | 17 or later | Runtime for Spring Boot |
| Maven | 3.8+ | Build and dependency management |
| Git | 2.30+ | Version control |
| Qoder IDE Plugin | Latest | AI coding assistant in your IDE |
| IDE | IntelliJ IDEA or VS Code | Development environment |
| Web Browser | Chrome / Edge / Firefox | Testing the application UI |

#### Verify Your Environment

Open a terminal and run the following commands to confirm everything is ready:

```bash
java -version
mvn -version
git --version
```

#### Initialize the Project Workspace

```bash
mkdir qoder-order-demo
cd qoder-order-demo
git init
echo "# Qoder Order System Demo" > README.md
git add .
git commit -m "Initial commit"
```

> 🎤 **Instructor Note:** Walk through the environment check live. If participants have issues, allocate 5–10 minutes for troubleshooting. Pre-built starter projects can be distributed as a fallback.

---

### 5. Step 1 – Generate the Order System

**Goal:** Use AI to generate a fully working Spring Boot order pricing system with a modern, professional UI.

#### 5.1 The Prompt

Open Qoder in your IDE and enter the following prompt:

```
Generate a Spring Boot order management system with the following requirements:

1. Backend (Spring Boot 3.x, Java 17):
   - A REST controller at /api/orders/calculate that accepts an order request and returns pricing details
   - An OrderRequest DTO with fields: productName, customerName, customerType (REGULAR, VIP, PREMIUM), quantity (int), discountCode (String), shippingMethod (STANDARD, EXPRESS, OVERNIGHT)
   - An OrderResponse DTO with fields: productName, customerName, unitPrice, quantity, subtotal, discountAmount, discountDescription, vipDiscountAmount, taxAmount, shippingFee, finalPrice
   - A PricingService that calculates:
     - Unit price: based on a simple product price map (e.g., Laptop=999.99, Phone=699.99, Tablet=499.99, Headphones=149.99, Monitor=349.99)
     - Subtotal: unitPrice × quantity
     - Discount codes: SAVE10 = 10% off, SAVE20 = 20% off, WELCOME = 15% off
     - VIP discount: REGULAR = 0%, VIP = 5%, PREMIUM = 10% (applied after discount code)
     - Tax: 8% of the amount after discounts
     - Shipping: STANDARD = free, EXPRESS = $15.00, OVERNIGHT = $30.00
     - Final price: amount after discounts + tax + shipping

2. Frontend (single HTML page served from src/main/resources/static/index.html):
   - A modern, clean, professional SaaS-style order form
   - Use a CSS framework feel (custom CSS is fine, no external dependencies needed)
   - Include a gradient header bar with the title "Order Pricing Calculator"
   - Form fields: Product (dropdown), Customer Name (text input), Customer Type (dropdown: Regular, VIP, Premium), Quantity (number input), Discount Code (text input), Shipping Method (dropdown: Standard, Express, Overnight)
   - A styled "Calculate Price" button
   - A results panel that appears below the form showing all pricing breakdown items in a clean card layout
   - The design should use a color scheme of blues and whites with subtle shadows and rounded corners
   - Include hover effects on the button and smooth transitions

3. Project structure should follow standard Maven conventions.

Please generate the complete project including pom.xml, application.properties, all Java classes, and the index.html file.
```

#### 5.2 Expected Project Structure

After AI generates the code, your project should look like this:

```
qoder-order-demo/
├── pom.xml
├── src/
│   └── main/
│       ├── java/
│       │   └── com/example/orderpricing/
│       │       ├── OrderPricingApplication.java
│       │       ├── controller/
│       │       │   └── OrderController.java
│       │       ├── dto/
│       │       │   ├── OrderRequest.java
│       │       │   └── OrderResponse.java
│       │       └── service/
│       │           └── PricingService.java
│       └── resources/
│           ├── application.properties
│           └── static/
│               └── index.html
```

#### 5.3 Run the Application

```bash
mvn spring-boot:run
```

Open your browser and navigate to:

```
http://localhost:8080
```

#### 5.4 Verify the UI

You should see a modern, professional order form with:

- A gradient header bar titled "Order Pricing Calculator"
- Dropdown selectors for Product, Customer Type, and Shipping Method
- Text inputs for Customer Name and Discount Code
- A number input for Quantity
- A styled "Calculate Price" button

Try submitting an order with these test values:

| Field | Value |
|-------|-------|
| Product | Laptop |
| Customer Name | Alice Johnson |
| Customer Type | VIP |
| Quantity | 3 |
| Discount Code | SAVE20 |
| Shipping Method | EXPRESS |

**Expected Result:**

The results panel should display a pricing breakdown similar to:

```
Product:          Laptop
Customer:         Alice Johnson
Unit Price:       $999.99
Quantity:         3
Subtotal:         $2,999.97
Discount (SAVE20): -$599.99
VIP Discount (5%):  -$120.00
Tax (8%):         $182.40
Shipping (EXPRESS): $15.00
─────────────────────────
Final Price:      $2,477.38
```

> 🎤 **Instructor Note:** This is the "wow moment." Emphasize that AI generated the entire application — backend logic, REST API, pricing calculations, and a polished UI — from a single prompt. Pause to let participants explore the UI and try different combinations.

#### 5.5 Git Commit and Tag

```bash
git add .
git commit -m "Step 1: Generate order pricing system with AI"
git tag demo-v1-running
```

---

### 6. Step 2 – Add a New Feature (Order Remark)

**Goal:** Use AI to modify the existing system by adding a new "Order Remark" field, demonstrating how AI handles incremental feature development.

#### 6.1 The Prompt

In Qoder, with the project context loaded, enter:

```
Add a new feature to the order system: an "Order Remark" field.

Changes needed:
1. Add a "remark" field (String) to the OrderRequest DTO
2. Add a "remark" field (String) to the OrderResponse DTO — it should be passed through from the request
3. Update the PricingService to carry the remark value into the response
4. Update the frontend UI to include a textarea input labeled "Order Remark" between the Shipping Method dropdown and the Calculate button
5. Display the remark in the results panel if it is not empty

The textarea should have placeholder text: "Enter any special instructions or notes for this order..."
It should match the existing form styling.
```

#### 6.2 Expected Changes

**OrderRequest.java** — new field added:

```java
private String remark;
```

**OrderResponse.java** — new field added:

```java
private String remark;
```

**PricingService.java** — the remark value is passed through from request to response.

**index.html** — a styled textarea appears in the form, and the remark shows in the results panel when present.

#### 6.3 Verify the Change

Restart the application:

```bash
mvn spring-boot:run
```

Fill out the form including a remark such as "Please gift-wrap this order" and calculate the price. The results panel should now include the remark text.

> 🎤 **Instructor Note:** Highlight that AI understood the existing project structure and made targeted changes across multiple files. This is feature-level modification, not just code generation. Point out that the AI maintained consistent styling in the UI update.

#### 6.4 Git Commit and Tag

```bash
git add .
git commit -m "Step 2: Add Order Remark feature via AI"
git tag demo-v2-feature
```

---

### 7. Step 3 – Understand the System Architecture

**Goal:** Ask AI to explain the system architecture, simulating an onboarding scenario where a new developer needs to understand the codebase.

#### 7.1 Prompts to Use

Use the following prompts one at a time in Qoder. Each demonstrates a different aspect of AI-powered code comprehension.

**Prompt 1 — High-Level Architecture:**

```
Explain the overall architecture of this Spring Boot order pricing system. 
Describe the layers (controller, service, DTO), how they interact, 
and how a request flows from the browser to the backend and back.
```

**Prompt 2 — Pricing Logic Deep Dive:**

```
Walk me through the pricing calculation flow in detail. 
How is the final price computed step by step? 
What discount logic is applied, and in what order?
```

**Prompt 3 — Frontend-Backend Interaction:**

```
Explain how the frontend (index.html) communicates with the backend. 
What API endpoint is called? What data format is used? 
How are the results rendered on the page?
```

**Prompt 4 — Generate a Diagram:**

```
Generate an ASCII architecture diagram showing the request flow 
from the browser through the controller, service, and DTOs, 
and back to the browser with the response.
```

#### 7.2 Expected Architecture Diagram

AI should produce something similar to this:

```
┌──────────────┐     HTTP POST          ┌──────────────────┐
│              │  /api/orders/calculate  │                  │
│   Browser    │ ─────────────────────→  │ OrderController   │
│  (index.html)│                        │                  │
│              │ ←─────────────────────  │  @PostMapping    │
└──────────────┘     JSON Response      └────────┬─────────┘
                                                 │
                                                 │ calls
                                                 ▼
                                        ┌──────────────────┐
                                        │                  │
                                        │ PricingService   │
                                        │                  │
                                        │ - lookupPrice()  │
                                        │ - applyDiscount()│
                                        │ - applyVIP()     │
                                        │ - calculateTax() │
                                        │ - addShipping()  │
                                        │                  │
                                        └──────────────────┘

    DTOs:
    ┌────────────────┐         ┌─────────────────┐
    │ OrderRequest   │         │ OrderResponse    │
    │                │         │                  │
    │ productName    │         │ unitPrice        │
    │ customerName   │         │ subtotal         │
    │ customerType   │         │ discountAmount   │
    │ quantity       │         │ vipDiscount      │
    │ discountCode   │         │ taxAmount        │
    │ shippingMethod │         │ shippingFee      │
    │ remark         │         │ finalPrice       │
    └────────────────┘         │ remark           │
                               └─────────────────┘
```

#### 7.3 Discussion Points

After reviewing the AI-generated explanations, consider these questions:

- Was the explanation accurate and complete?
- Would this be useful for onboarding a new developer?
- How does this compare to manually written documentation?
- Could this be automated as part of a documentation pipeline?

> 🎤 **Instructor Note:** This step is powerful for non-technical stakeholders. It shows AI can bridge the gap between code and comprehension. For technical audiences, emphasize that this scales — imagine running this across hundreds of microservices to generate up-to-date architecture docs automatically.

---

### 8. Step 4 – AI Code Review

**Goal:** Use AI to perform a code review of the pricing logic, demonstrating how AI catches real-world quality issues.

#### 8.1 IDE-Based Review

In Qoder within your IDE, enter the following prompt:

```
Review the PricingService class for potential issues. 
Focus on:
- Input validation
- Numerical precision for currency calculations
- Edge cases
- Error handling
- Missing unit tests
- Security concerns

Provide specific recommendations with code examples for each issue found.
```

#### 8.2 Expected Issues Identified

AI should identify issues such as these:

**Issue 1 — No Input Validation**

The service does not validate that quantity is positive, or that required fields are not null.

```java
// Recommended fix
if (request.getQuantity() <= 0) {
    throw new IllegalArgumentException("Quantity must be greater than zero");
}
if (request.getProductName() == null || request.getProductName().isBlank()) {
    throw new IllegalArgumentException("Product name is required");
}
```

**Issue 2 — Floating-Point Precision**

Using `double` for currency calculations can cause rounding errors (e.g., 0.1 + 0.2 ≠ 0.3).

```java
// Current (problematic)
double subtotal = unitPrice * quantity;

// Recommended (use BigDecimal)
BigDecimal subtotal = BigDecimal.valueOf(unitPrice)
    .multiply(BigDecimal.valueOf(quantity))
    .setScale(2, RoundingMode.HALF_UP);
```

**Issue 3 — No Unit Tests**

There are no tests for the pricing logic. AI should suggest test cases covering normal orders, all discount codes, VIP tiers, edge cases (quantity = 1, unknown product), and boundary conditions.

**Issue 4 — Unknown Product / Discount Code Handling**

If an unrecognized product name or discount code is provided, the behavior is undefined. The service should return a clear error or a default value.

#### 8.3 CLI-Based Review

Beyond IDE use, Qoder can be invoked from the command line for automated reviews.

```bash
# Generate a diff of recent changes
git diff demo-v1-running..demo-v2-feature > changes.patch

# Run Qoder CLI review
qoder review changes.patch
```

#### 8.4 IDE vs. CLI Review — Key Differences

| Aspect | IDE-Based Review | CLI-Based Review |
|--------|-----------------|-----------------|
| **Trigger** | Manual, developer-initiated | Automated, pipeline-triggered |
| **Context** | Full project context in IDE | Scoped to diff / patch file |
| **Interaction** | Conversational, iterative | One-shot, report-based |
| **Best For** | During development | During code review / CI |
| **Output** | Inline suggestions in editor | Structured report (JSON/text) |

> 🎤 **Instructor Note:** This is where enterprise value becomes tangible. IDE review helps individual developers; CLI review enforces quality across teams. For business audiences, emphasize: "Every pull request gets a free senior engineer review."

#### 8.5 Git Commit and Tag

```bash
git add .
git commit -m "Step 4: Apply AI code review recommendations"
git tag demo-v3-review
```

---

### 9. Step 5 – Microservice Refactoring

**Goal:** Evolve the monolithic application into two microservices — `order-service` and `pricing-service` — demonstrating AI-assisted architectural refactoring.

#### 9.1 Target Architecture

```
┌──────────────┐       ┌──────────────────┐       ┌──────────────────┐
│              │       │                  │       │                  │
│   Browser    │──────→│  order-service   │──────→│ pricing-service  │
│              │       │   (port 8080)    │       │   (port 8081)    │
│              │←──────│                  │←──────│                  │
└──────────────┘       └──────────────────┘       └──────────────────┘
                              │                          │
                        Serves the UI            Pricing calculation
                        Accepts order requests   REST API endpoint
                        Calls pricing-service    /api/pricing/calculate
```

#### 9.2 The Prompt

```
Refactor this order pricing system into two separate Spring Boot microservices:

1. order-service (port 8080):
   - Serves the frontend UI (index.html)
   - Exposes the /api/orders/calculate endpoint
   - Receives the order request from the browser
   - Calls pricing-service via REST to get pricing details
   - Returns the combined response to the browser
   - Uses RestTemplate or WebClient to call pricing-service

2. pricing-service (port 8081):
   - Contains the PricingService logic
   - Exposes a /api/pricing/calculate endpoint
   - Receives a pricing request and returns pricing breakdown
   - Has no UI — purely an API service

Create the two projects as separate Maven modules or directories:
- order-service/
- pricing-service/

Each should have its own pom.xml, application.properties, and complete source code.
The frontend should remain unchanged and still work the same way from the user's perspective.
```

#### 9.3 Expected Project Structure

```
qoder-order-demo/
├── order-service/
│   ├── pom.xml
│   └── src/main/
│       ├── java/com/example/orderservice/
│       │   ├── OrderServiceApplication.java
│       │   ├── controller/
│       │   │   └── OrderController.java
│       │   ├── dto/
│       │   │   ├── OrderRequest.java
│       │   │   └── OrderResponse.java
│       │   └── client/
│       │       └── PricingClient.java
│       └── resources/
│           ├── application.properties  (server.port=8080)
│           └── static/
│               └── index.html
│
├── pricing-service/
│   ├── pom.xml
│   └── src/main/
│       ├── java/com/example/pricingservice/
│       │   ├── PricingServiceApplication.java
│       │   ├── controller/
│       │   │   └── PricingController.java
│       │   ├── dto/
│       │   │   ├── PricingRequest.java
│       │   │   └── PricingResponse.java
│       │   └── service/
│       │       └── PricingService.java
│       └── resources/
│           └── application.properties  (server.port=8081)
```

#### 9.4 Run Both Services

Open two terminal windows.

**Terminal 1 — Start pricing-service first:**

```bash
cd pricing-service
mvn spring-boot:run
```

**Terminal 2 — Start order-service:**

```bash
cd order-service
mvn spring-boot:run
```

Navigate to `http://localhost:8080` and verify that the order form works exactly as before. The difference is now invisible to the user — the pricing logic runs in a separate service.

#### 9.5 Verify the Microservice Communication

You can verify that `pricing-service` is being called independently:

```bash
curl -X POST http://localhost:8081/api/pricing/calculate \
  -H "Content-Type: application/json" \
  -d '{
    "productName": "Laptop",
    "customerType": "VIP",
    "quantity": 2,
    "discountCode": "SAVE10",
    "shippingMethod": "STANDARD"
  }'
```

This should return a JSON pricing breakdown directly from the pricing service.

> 🎤 **Instructor Note:** This step demonstrates AI's ability to perform complex structural refactoring — not just writing new code, but decomposing an existing system. Emphasize that this is one of the most time-consuming tasks developers face, and AI significantly accelerates it. Point out that the user experience is unchanged, which is the hallmark of a good refactoring.

#### 9.6 Git Commit and Tag

```bash
git add .
git commit -m "Step 5: Refactor into order-service and pricing-service microservices"
git tag demo-v4-microservice
```

---

### 10. Step 6 – CI/CD Integration Concept

**Goal:** Understand how AI code review can be embedded into CI/CD pipelines for automated quality enforcement.

#### 10.1 The Concept

In a production environment, code reviews should not rely solely on individual developers remembering to ask AI for feedback. Instead, AI code review can be triggered automatically on every pull request through CI/CD integration.

The workflow looks like this:

```
Developer pushes code
        │
        ▼
Pull Request created
        │
        ▼
CI Pipeline triggers
        │
        ▼
┌─────────────────────┐
│  Qoder CLI executes  │
│  automated review    │
│  on the PR diff      │
└─────────┬───────────┘
          │
          ▼
Code Review Report
generated as PR comment
```

#### 10.2 Jenkins Pipeline Example

```groovy
pipeline {
    agent any

    stages {
        stage('Build') {
            steps {
                sh 'mvn clean compile'
            }
        }

        stage('Test') {
            steps {
                sh 'mvn test'
            }
        }

        stage('AI Code Review') {
            steps {
                sh '''
                    git diff origin/main...HEAD > diff.patch
                    qoder review diff.patch --output report.json
                '''
            }
        }

        stage('Publish Review') {
            steps {
                script {
                    def report = readJSON file: 'report.json'
                    if (report.severity == 'HIGH') {
                        error "AI Code Review found high-severity issues. Please address them before merging."
                    }
                }
            }
        }
    }
}
```

#### 10.3 GitHub Actions Example

```yaml
name: AI Code Review

on:
  pull_request:
    branches: [ main ]

jobs:
  ai-review:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Generate diff
        run: git diff origin/main...HEAD > diff.patch

      - name: Run Qoder AI Review
        run: qoder review diff.patch --output report.json

      - name: Comment on PR
        uses: actions/github-script@v7
        with:
          script: |
            const fs = require('fs');
            const report = JSON.parse(fs.readFileSync('report.json', 'utf8'));
            await github.rest.issues.createComment({
              owner: context.repo.owner,
              repo: context.repo.repo,
              issue_number: context.issue.number,
              body: `## AI Code Review Report\n\n${report.summary}`
            });
```

#### 10.4 Key Benefits for Enterprise Teams

**Consistency** — Every pull request receives the same level of scrutiny, regardless of reviewer availability or workload.

**Speed** — AI review completes in seconds, not hours or days. Developers get feedback while the code is still fresh in their minds.

**Coverage** — AI can check for issues that human reviewers might overlook: precision errors, missing edge cases, security patterns, and adherence to coding standards.

**Scalability** — Whether your team submits 5 or 500 pull requests per week, AI review scales without additional headcount.

> 🎤 **Instructor Note:** This is the "enterprise pitch" step. For business stakeholders, frame it as: "AI code review becomes a quality gate — like automated tests, but for code quality and best practices." For technical audiences, emphasize the pipeline integration simplicity and the ability to customize review rules.

---

### 11. Git Versioning Strategy

Throughout this lab, you have been creating Git commits and tags to mark each milestone. Here is the complete versioning strategy:

| Tag | Stage | Description |
|-----|-------|-------------|
| `demo-v1-running` | Step 1 | Initial system generated by AI — fully working order pricing app |
| `demo-v2-feature` | Step 2 | New "Order Remark" feature added via AI |
| `demo-v3-review` | Step 4 | Code review fixes applied (validation, BigDecimal, tests) |
| `demo-v4-microservice` | Step 5 | System refactored into order-service and pricing-service |

#### Navigating Between Versions

At any point, you can switch between versions to compare the system at different stages:

```bash
# View all tags
git tag -l

# Switch to a specific version
git checkout demo-v1-running

# Return to the latest version
git checkout main
```

#### Comparing Changes Between Stages

```bash
# See what changed between v1 and v2 (the Order Remark feature)
git diff demo-v1-running..demo-v2-feature

# See what changed during the microservice refactoring
git diff demo-v3-review..demo-v4-microservice

# View commit log with tags
git log --oneline --decorate
```

This versioning approach allows presenters to jump to any stage of the demo instantly, and gives participants a clear history of how the system evolved.

---

### 12. Troubleshooting

#### "Port 8080 already in use"

Another process is using port 8080. Find and stop it:

```bash
# macOS / Linux
lsof -i :8080
kill -9 <PID>

# Or change the port in application.properties
server.port=8090
```

#### "mvn: command not found"

Maven is not installed or not in your PATH. Install it:

```bash
# macOS
brew install maven

# Or download from https://maven.apache.org/download.cgi
```

#### Frontend Not Loading (Blank Page)

Ensure the `index.html` file is in the correct location: `src/main/resources/static/index.html`. Spring Boot automatically serves static files from this directory.

#### CORS Errors in Browser Console

If you see CORS errors after the microservice refactoring (Step 5), add CORS configuration to `pricing-service`:

```java
@CrossOrigin(origins = "http://localhost:8080")
@RestController
public class PricingController {
    // ...
}
```

#### pricing-service Connection Refused

Make sure `pricing-service` is running on port 8081 before starting `order-service`. Check that `order-service` is configured with the correct URL:

```properties
# order-service application.properties
pricing.service.url=http://localhost:8081/api/pricing/calculate
```

#### Java Version Mismatch

If you see compilation errors related to language features, verify you are using JDK 17+:

```bash
java -version
# Should show 17 or higher
```

---

### 13. Instructor Notes

#### Overall Presentation Strategy

This lab is designed to tell a story: a developer's journey from "I have a requirement" to "I have a production-ready, well-reviewed, microservice-based system" — with AI as a collaborator at every step.

#### Stage-by-Stage Guidance

**Step 1 (Generate the System) — The "Wow" Moment**

This is your strongest opening. The audience sees a complete, polished application appear from a single prompt. Let the generated UI speak for itself — it looks professional, it works, and it took seconds. Give participants time to interact with it and try different inputs. This step resonates with everyone — developers, managers, and executives alike.

**Step 2 (Add a Feature) — Incremental AI Development**

This step shows that AI is not just for greenfield projects. It can understand existing code and make targeted, consistent changes across multiple files. Emphasize that the AI maintained the existing code style and UI design. For technical audiences, highlight the multi-file coordination (DTO, service, and frontend).

**Step 3 (Architecture Explanation) — AI as Documentation Tool**

This step is particularly powerful for two audiences. For technical leaders, it demonstrates how AI can generate onboarding documentation automatically. For business stakeholders, it shows that AI reduces the "bus factor" — knowledge is no longer locked in one developer's head. This step requires no code changes, making it a good resting point in the lab.

**Step 4 (Code Review) — Enterprise Quality**

This is where enterprise decision-makers pay close attention. The AI identifies real issues — not hypothetical problems, but the kind of bugs that make it to production (floating-point precision in financial calculations, missing input validation). Emphasize the difference between IDE review (developer workflow) and CLI review (team workflow). The CLI approach naturally leads into Step 6.

**Step 5 (Microservice Refactoring) — Architectural Evolution**

This is the most technically impressive step. AI decomposes a monolith into two services, sets up inter-service communication, and maintains functional equivalence. For senior developers and architects, this demonstrates that AI can handle structural complexity, not just line-level code generation. For business audiences, frame it as: "Migration projects that used to take weeks can be accelerated to hours."

**Step 6 (CI/CD Integration) — Scalable Quality**

This is a conceptual step — no hands-on coding required. Use it to paint the vision of AI-augmented development at scale. Show the Jenkins and GitHub Actions examples. For enterprise audiences, connect it to existing DevOps practices: "You already have automated tests in your pipeline. Now add automated code review."

#### Audience Adaptation Guide

**For Developer Audiences:** Spend more time on Steps 1, 2, 4, and 5. Developers want to see the prompts, understand the generated code, and explore edge cases. Encourage them to modify prompts and compare results.

**For Technical Leaders / Architects:** Emphasize Steps 3, 5, and 6. These demonstrate documentation automation, architectural refactoring, and pipeline integration — the capabilities that scale across teams.

**For Business Stakeholders:** Focus on Steps 1, 4, and 6. Lead with the speed of generation (Step 1), the quality assurance value (Step 4), and the organizational scale (Step 6). Keep code details minimal; focus on outcomes and ROI.

#### Timing Guide

| Section | Full Lab | Short Demo |
|---------|----------|------------|
| Setup | 15 min | 5 min |
| Step 1 – Generate | 30 min | 15 min |
| Step 2 – Feature | 20 min | 10 min |
| Step 3 – Architecture | 15 min | 5 min |
| Step 4 – Code Review | 25 min | 10 min |
| Step 5 – Microservices | 30 min | 10 min |
| Step 6 – CI/CD | 15 min | 5 min |
| Q&A | 15 min | 10 min |
| **Total** | **~2.75 hrs** | **~1.1 hrs** |

#### IDE vs. CLI — How to Explain the Difference

Use this analogy: "The IDE integration is like having a knowledgeable colleague sitting next to you — you can ask questions and get immediate help. The CLI integration is like having that same colleague automatically review every pull request your entire team creates. One helps individual developers; the other raises the quality bar for the whole organization."

---

### 14. Summary

In this lab, you experienced the full spectrum of AI-assisted software development:

| Stage | What You Did | AI Capability Demonstrated |
|-------|-------------|---------------------------|
| Step 1 | Generated a complete order system | Code generation with UI |
| Step 2 | Added the Order Remark feature | Contextual code modification |
| Step 3 | Explored the architecture | Code comprehension & documentation |
| Step 4 | Reviewed pricing logic | Automated code review |
| Step 5 | Refactored to microservices | Architectural refactoring |
| Step 6 | Explored CI/CD integration | Pipeline automation |

The key takeaway is that AI is not replacing developers — it is amplifying them. Each step in this lab represents a task that developers already do. AI makes these tasks faster, more consistent, and more accessible. From generating a first prototype to reviewing code quality to refactoring architecture, AI serves as a tireless collaborator that scales with your team.

Your final Git history tells the story:

```bash
git log --oneline --decorate
# abc1234 (tag: demo-v4-microservice) Step 5: Refactor into microservices
# def5678 (tag: demo-v3-review) Step 4: Apply AI code review recommendations
# ghi9012 (tag: demo-v2-feature) Step 2: Add Order Remark feature via AI
# jkl3456 (tag: demo-v1-running) Step 1: Generate order pricing system with AI
# mno7890 Initial commit
```

Thank you for participating in this hands-on lab. You are now equipped to bring AI-assisted development practices into your own projects and teams.

---

*Qoder AI Coding Hands-on Lab Guide — Version 1.0*
