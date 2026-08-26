// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "facman_release_route_permit_gate.h"

#include "fl_operation_permit.h"
#include "fl_sha256.h"

#include <algorithm>
#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>
#include <thread>

namespace fs = std::filesystem;
namespace permit = facman::core::permit;
namespace route = facman::release_route;

namespace {

class FixtureClock final : public permit::PermitClock {
public:
    std::uint64_t wall = 1000U;
    std::uint64_t monotonic = 5000U;
    std::uint64_t unix_seconds() const override { return wall; }
    std::uint64_t monotonic_milliseconds() const override { return monotonic; }
};

struct Fixture {
    fs::path root;
    fs::path claims;
    fs::path receipts;

    explicit Fixture(const std::string& name)
    {
        const auto nonce = std::chrono::steady_clock::now().time_since_epoch().count();
        root = fs::temp_directory_path() / "facman-route-permit-gate-smoke" /
            (name + "-" + std::to_string(nonce));
        claims = root / "claims";
        receipts = root / "receipts";
        fs::create_directories(claims);
        fs::create_directories(receipts);
    }

    ~Fixture()
    {
        std::error_code ignored;
        fs::remove_all(root, ignored);
    }
};

std::string digest(const std::string& value)
{
    return facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(value.data()), value.size());
}

std::string custody_text()
{
    return "{\"schema\":\"facman.route_permit_session_custody.v1\","
        "\"issuer_session_id\":\"session-22222222222222222222222222222222\","
        "\"key_hex\":\"1111111111111111111111111111111111111111111111111111111111111111\"}";
}

permit::PermitValidationContext context(const std::string& plan_id)
{
    permit::PermitValidationContext value;
    value.operation = {"instance.play", "menu", "sandbox_task_owned_instance"};
    value.plan = {plan_id, digest(plan_id + ":attempt-1:launch")};
    value.consumer = {"factorio.launch.local", "release-route-harness.v2"};
    value.resources = {{
        "factorio.executable", "process_image", "factorio-2.1.14.exe",
        std::string(64U, '3'), value.consumer, {"process_execute"}}};
    value.effects = {"process_execute", "workspace_read", "workspace_write"};
    value.required_capabilities = {"launch.execute.sandbox", "process.execute"};
    value.machine_binding_id = "facman.successor-play.clean-host.03";
    value.principal = {
        "facman.release-route-control", "Jules", "route-operation-session-1"};
    value.evidence_digest = std::string(64U, '4');
    value.policy = {"1", std::string(64U, '5')};
    value.provider_revisions = {
        value.consumer,
        {"facman.release-route-control", "host-guest-two-phase.v1"}};
    return value;
}

permit::OperationPermitClaims claims(
    const permit::PermitValidationContext& expected,
    const std::string& permit_suffix = std::string(32U, 'a'))
{
    permit::OperationPermitClaims value;
    value.permit_id = "permit-" + permit_suffix;
    value.issuer_session_id = "session-22222222222222222222222222222222";
    value.operation = expected.operation;
    value.plan = expected.plan;
    value.audience = expected.consumer;
    value.resources = expected.resources;
    value.effects = expected.effects;
    value.required_capabilities = expected.required_capabilities;
    value.machine_binding_id = expected.machine_binding_id;
    value.principal = expected.principal;
    value.evidence_digest = expected.evidence_digest;
    value.policy = expected.policy;
    value.provider_revisions = expected.provider_revisions;
    value.issued_at_unix_seconds = 1000U;
    value.not_before_unix_seconds = 1000U;
    value.expires_at_unix_seconds = 1060U;
    value.nonce = "nonce-bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb";
    return value;
}

std::string encode(
    const permit::OperationPermitClaims& value,
    const permit::PermitAuthenticator& authenticator)
{
    auto sealed = permit::seal_claims(value, authenticator);
    if (!sealed) throw std::runtime_error(sealed.error().code);
    auto text = permit::envelope_json(sealed.value());
    if (!text) throw std::runtime_error(text.error().code);
    return text.take_value();
}

route::RoutePermitConsumeRequest request(
    Fixture& fixture,
    const permit::PermitValidationContext& expected,
    const std::string& envelope,
    const std::string& suffix)
{
    return {
        envelope,
        digest(envelope),
        expected,
        fixture.claims,
        fixture.receipts / ("consume-" + suffix + ".json"),
        fixture.receipts / ("refuse-" + suffix + ".json")};
}

bool refused(
    route::RoutePermitConsumeRequest value,
    const permit::PermitAuthenticator& authenticator,
    const permit::PermitClock& clock,
    const std::string& code)
{
    int dispatches = 0;
    const auto outcome = route::consume_route_permit(value, authenticator, clock);
    if (outcome.consumed) ++dispatches;
    return dispatches == 0 && !outcome.consumed && outcome.code == code &&
        fs::is_regular_file(value.refusal_receipt);
}

int basic_and_replay(
    const permit::PermitAuthenticator& authenticator,
    const FixtureClock& clock)
{
    Fixture fixture("basic");
    const auto expected = context("facman.successor-play.launch-1.operation.03");
    const std::string envelope = encode(claims(expected), authenticator);
    auto first = request(fixture, expected, envelope, "first");
    int dispatches = 0;
    const auto consumed = route::consume_route_permit(first, authenticator, clock);
    if (consumed.consumed) ++dispatches;
    if (dispatches != 1 || consumed.code != "permit_consumed" ||
        !fs::is_regular_file(first.consume_receipt) ||
        !fs::is_regular_file(consumed.claim_record)) return 10;
    auto replay = request(fixture, expected, envelope, "replay");
    if (!refused(replay, authenticator, clock, "permit_replayed")) return 11;
    return 0;
}

int malformed_and_authentication(
    const permit::PermitAuthenticator& authenticator,
    const FixtureClock& clock)
{
    const auto expected = context("facman.successor-play.launch-1.operation.03");
    const std::string valid = encode(claims(expected), authenticator);
    {
        Fixture fixture("missing");
        if (!refused(request(fixture, expected, "", "missing"),
                authenticator, clock, "permit_missing")) return 20;
    }
    {
        Fixture fixture("digest");
        auto value = request(fixture, expected, valid, "digest");
        value.envelope_sha256 = std::string(64U, '0');
        if (!refused(value, authenticator, clock, "permit_envelope_digest_mismatch")) return 21;
    }
    {
        Fixture fixture("malformed");
        const std::string malformed = "{}";
        auto value = request(fixture, expected, malformed, "malformed");
        const auto outcome = route::consume_route_permit(value, authenticator, clock);
        if (outcome.consumed || !fs::is_regular_file(value.refusal_receipt)) return 22;
    }
    {
        Fixture fixture("unknown");
        std::string changed = valid;
        changed.insert(changed.size() - 1U, ",\"unknown\":true");
        auto value = request(fixture, expected, changed, "unknown");
        const auto outcome = route::consume_route_permit(value, authenticator, clock);
        if (outcome.consumed || !fs::is_regular_file(value.refusal_receipt)) return 23;
    }
    {
        Fixture fixture("payload");
        auto changed_claims = claims(expected);
        changed_claims.plan.plan_digest = std::string(64U, '6');
        std::string changed = encode(changed_claims, authenticator);
        if (!refused(request(fixture, expected, changed, "payload"),
                authenticator, clock, "permit_wrong_plan")) return 24;
    }
    {
        Fixture fixture("signature");
        auto sealed = permit::seal_claims(claims(expected), authenticator);
        if (!sealed) return 25;
        sealed.value().authenticator_value[0] =
            sealed.value().authenticator_value[0] == '0' ? '1' : '0';
        auto changed = permit::envelope_json(sealed.value());
        if (!changed || !refused(request(fixture, expected, changed.value(), "signature"),
                authenticator, clock, "permit_authentication_failed")) return 26;
    }
    return 0;
}

int time_and_cross_launch(
    const permit::PermitAuthenticator& authenticator,
    const FixtureClock& clock)
{
    const auto first = context("facman.successor-play.launch-1.operation.03");
    {
        Fixture fixture("expired");
        auto value = claims(first);
        value.issued_at_unix_seconds = 800U;
        value.not_before_unix_seconds = 800U;
        value.expires_at_unix_seconds = 900U;
        if (!refused(request(fixture, first, encode(value, authenticator), "expired"),
                authenticator, clock, "permit_expired")) return 30;
    }
    {
        Fixture fixture("future");
        auto value = claims(first);
        value.not_before_unix_seconds = 1010U;
        value.expires_at_unix_seconds = 1070U;
        if (!refused(request(fixture, first, encode(value, authenticator), "future"),
                authenticator, clock, "permit_not_yet_valid")) return 31;
    }
    {
        Fixture fixture("ttl");
        auto value = claims(first);
        value.expires_at_unix_seconds = 1121U;
        if (!refused(request(fixture, first, encode(value, authenticator), "ttl"),
                authenticator, clock, "permit_lifetime_exceeded")) return 32;
    }
    {
        Fixture fixture("cross-launch");
        auto second = context("facman.successor-play.launch-2.operation.03");
        if (!refused(request(fixture, second, encode(claims(first), authenticator), "cross"),
                authenticator, clock, "permit_wrong_plan")) return 33;
    }
    {
        Fixture fixture("wrong-operation");
        auto wrong = first;
        wrong.operation.kind = "instance.repair";
        if (!refused(request(fixture, wrong, encode(claims(first), authenticator), "operation"),
                authenticator, clock, "permit_wrong_operation")) return 34;
    }
    return 0;
}

int atomic_and_receipt_failure(
    const permit::PermitAuthenticator& authenticator,
    const FixtureClock& clock)
{
    const auto expected = context("facman.successor-play.launch-1.operation.03");
    const std::string envelope = encode(claims(expected), authenticator);
    {
        Fixture fixture("concurrent");
        auto left_request = request(fixture, expected, envelope, "left");
        auto right_request = request(fixture, expected, envelope, "right");
        route::RoutePermitConsumeOutcome left;
        route::RoutePermitConsumeOutcome right;
        std::thread first([&] {
            left = route::consume_route_permit(left_request, authenticator, clock);
        });
        std::thread second([&] {
            right = route::consume_route_permit(right_request, authenticator, clock);
        });
        first.join();
        second.join();
        const int consumed = static_cast<int>(left.consumed) + static_cast<int>(right.consumed);
        const int replayed = static_cast<int>(left.code == "permit_replayed") +
            static_cast<int>(right.code == "permit_replayed");
        if (consumed != 1 || replayed != 1) return 40;
    }
    {
        Fixture fixture("crash-claim");
        const fs::path claim = fixture.claims /
            (claims(expected).permit_id + ".claimed.v1.json");
        std::ofstream output(claim, std::ios::binary);
        output << "{\"status\":\"claiming_interrupted\"}";
        output.close();
        if (!refused(request(fixture, expected, envelope, "crash"),
                authenticator, clock, "permit_replayed")) return 41;
    }
    {
        Fixture fixture("receipt");
        auto value = request(fixture, expected, envelope, "receipt");
        std::ofstream existing(value.consume_receipt, std::ios::binary);
        existing << "occupied";
        existing.close();
        if (!refused(value, authenticator, clock,
                "permit_consume_receipt_write_failed")) return 42;
        if (std::count_if(fs::directory_iterator(fixture.claims), fs::directory_iterator(),
                [](const fs::directory_entry& item) { return item.is_regular_file(); }) != 1) {
            return 43;
        }
    }
    return 0;
}

} // namespace

int main()
{
    auto authenticator = route::CustodiedProcessAuthenticator::decode(custody_text());
    if (!authenticator) return 1;
    auto malformed = route::CustodiedProcessAuthenticator::decode("{}");
    if (malformed || malformed.error().code != "permit_session_custody_malformed") return 2;
    FixtureClock clock;
    if (const int result = basic_and_replay(*authenticator.value(), clock)) return result;
    if (const int result = malformed_and_authentication(*authenticator.value(), clock)) return result;
    if (const int result = time_and_cross_launch(*authenticator.value(), clock)) return result;
    if (const int result = atomic_and_receipt_failure(*authenticator.value(), clock)) return result;
    std::cout << "facman-release-route-permit-gate: ok; zero-dispatch refusals; atomic replay closed\n";
    return 0;
}
