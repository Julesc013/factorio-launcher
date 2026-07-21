// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#include "fl_operation_permit.h"

#include "fl_json.h"
#include "fl_sha256.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cctype>
#include <limits>
#include <map>
#include <mutex>
#include <set>
#include <tuple>
#include <utility>

namespace facman::core::permit {
namespace {

using facman::core::Error;
using facman::core::OutcomeKind;
using facman::core::Result;
namespace json = facman::core::json;

constexpr std::uint64_t kMaximumExactJsonInteger = 9007199254740991ULL;

Error malformed(std::string message, std::string path = "$claims")
{
    return {"permit_malformed", std::move(message), std::move(path), OutcomeKind::invalid_argument};
}

Error unsupported(std::string message, std::string path)
{
    return {"permit_schema_unsupported", std::move(message), std::move(path), OutcomeKind::refused};
}

bool lowercase_hex_digest(const std::string& value)
{
    return value.size() == 64U && std::all_of(value.begin(), value.end(), [](unsigned char byte) {
        return (byte >= '0' && byte <= '9') || (byte >= 'a' && byte <= 'f');
    });
}

bool prefixed_hex_id(const std::string& value, const char* prefix)
{
    const std::string expected(prefix);
    if (value.size() != expected.size() + 32U || value.compare(0, expected.size(), expected) != 0) return false;
    return std::all_of(value.begin() + static_cast<std::ptrdiff_t>(expected.size()), value.end(), [](unsigned char byte) {
        return (byte >= '0' && byte <= '9') || (byte >= 'a' && byte <= 'f');
    });
}

bool bounded_text(const std::string& value, std::size_t maximum)
{
    if (value.empty() || value.size() > maximum) return false;
    return std::none_of(value.begin(), value.end(), [](unsigned char byte) {
        return byte < 0x20U || byte == 0x7fU;
    });
}

bool dotted_identifier(const std::string& value, std::size_t maximum)
{
    if (value.size() < 3U || value.size() > maximum || value.front() < 'a' || value.front() > 'z') return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char byte) {
        return (byte >= 'a' && byte <= 'z') || (byte >= '0' && byte <= '9') ||
            byte == '.' || byte == '_' || byte == '-';
    });
}

bool resource_identifier(const std::string& value)
{
    if (value.size() < 2U || value.size() > 64U || value.front() < 'a' || value.front() > 'z') return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char byte) {
        return (byte >= 'a' && byte <= 'z') || (byte >= '0' && byte <= '9') ||
            byte == '.' || byte == '_' || byte == '-';
    });
}

bool provider_identifier(const std::string& value)
{
    if (value.size() < 3U || value.size() > 128U || value.front() < 'a' || value.front() > 'z') return false;
    return std::all_of(value.begin(), value.end(), [](unsigned char byte) {
        return (byte >= 'a' && byte <= 'z') || (byte >= '0' && byte <= '9') ||
            byte == '.' || byte == '-';
    });
}

bool allowed_effect(const std::string& value)
{
    static const std::set<std::string> effects = {
        "credential_read", "network_read", "network_write", "process_execute",
        "release_publish", "release_sign", "setup_mutation", "setup_preview",
        "workspace_read", "workspace_write"};
    return effects.find(value) != effects.end();
}

bool provider_equal(const ProviderIdentity& left, const ProviderIdentity& right)
{
    return left.provider_id == right.provider_id &&
        left.provider_revision == right.provider_revision;
}

bool provider_less(const ProviderIdentity& left, const ProviderIdentity& right)
{
    return std::tie(left.provider_id, left.provider_revision) <
        std::tie(right.provider_id, right.provider_revision);
}

bool principal_equal(const PrincipalIdentity& left, const PrincipalIdentity& right)
{
    return std::tie(left.provider_id, left.principal_id, left.application_session_id) ==
        std::tie(right.provider_id, right.principal_id, right.application_session_id);
}

bool policy_equal(const PolicyBinding& left, const PolicyBinding& right)
{
    return left.policy_revision == right.policy_revision &&
        left.policy_digest == right.policy_digest;
}

bool plan_equal(const PlanBinding& left, const PlanBinding& right)
{
    return left.plan_id == right.plan_id && left.plan_digest == right.plan_digest;
}

using ResourceKey = std::tuple<std::string, std::string, std::string>;

ResourceKey resource_key(const ResourceBinding& value)
{
    return {value.resource_kind, value.role, value.logical_id};
}

bool resource_less(const ResourceBinding& left, const ResourceBinding& right)
{
    return resource_key(left) < resource_key(right);
}

Result<std::vector<std::string>> canonical_string_set(
    std::vector<std::string> values,
    bool effects,
    const std::string& path)
{
    if (values.empty()) return Result<std::vector<std::string>>::failure(
        malformed("closed set must not be empty", path));
    for (const std::string& value : values) {
        if ((effects && !allowed_effect(value)) ||
            (!effects && !dotted_identifier(value, 128U))) {
            return Result<std::vector<std::string>>::failure(
                malformed("closed set contains an unsupported value", path));
        }
    }
    std::sort(values.begin(), values.end());
    if (std::adjacent_find(values.begin(), values.end()) != values.end()) {
        return Result<std::vector<std::string>>::failure(
            malformed("closed set contains a duplicate value", path));
    }
    return Result<std::vector<std::string>>::success(std::move(values));
}

Result<std::vector<ProviderIdentity>> canonical_providers(
    std::vector<ProviderIdentity> values,
    const std::string& path)
{
    if (values.empty()) return Result<std::vector<ProviderIdentity>>::failure(
        malformed("provider set must not be empty", path));
    for (const ProviderIdentity& value : values) {
        if (!provider_identifier(value.provider_id) ||
            !bounded_text(value.provider_revision, 128U)) {
            return Result<std::vector<ProviderIdentity>>::failure(
                malformed("provider identity is invalid", path));
        }
    }
    std::sort(values.begin(), values.end(), provider_less);
    for (std::size_t index = 1; index < values.size(); ++index) {
        if (values[index - 1U].provider_id == values[index].provider_id) {
            return Result<std::vector<ProviderIdentity>>::failure(
                malformed("provider set contains a duplicate provider", path));
        }
    }
    return Result<std::vector<ProviderIdentity>>::success(std::move(values));
}

Result<std::vector<ResourceBinding>> canonical_resources(
    std::vector<ResourceBinding> values,
    const std::vector<std::string>& claim_effects,
    const std::vector<ProviderIdentity>& providers)
{
    if (values.empty() || values.size() > 128U) {
        return Result<std::vector<ResourceBinding>>::failure({
            "permit_resource_set_not_closed", "permit resource set must contain 1-128 exact resources",
            "$claims.resources", OutcomeKind::refused});
    }
    for (ResourceBinding& value : values) {
        if (!resource_identifier(value.resource_kind) ||
            !resource_identifier(value.role) ||
            !bounded_text(value.logical_id, 256U) ||
            value.logical_id.find('*') != std::string::npos ||
            !lowercase_hex_digest(value.current_identity_digest) ||
            !provider_identifier(value.owning_provider.provider_id) ||
            !bounded_text(value.owning_provider.provider_revision, 128U)) {
            return Result<std::vector<ResourceBinding>>::failure({
                "permit_resource_set_not_closed", "permit resource binding is invalid or wildcarded",
                "$claims.resources", OutcomeKind::refused});
        }
        auto resource_effects = canonical_string_set(
            std::move(value.permitted_effects), true, "$claims.resources[].permitted_effects");
        if (!resource_effects) return Result<std::vector<ResourceBinding>>::failure({
            "permit_resource_set_not_closed", resource_effects.error().message,
            resource_effects.error().path, OutcomeKind::refused});
        value.permitted_effects = resource_effects.take_value();
        if (!std::includes(
                claim_effects.begin(), claim_effects.end(),
                value.permitted_effects.begin(), value.permitted_effects.end())) {
            return Result<std::vector<ResourceBinding>>::failure({
                "permit_effect_scope_mismatch", "resource effects exceed the permit effect set",
                "$claims.resources[].permitted_effects", OutcomeKind::refused});
        }
        const bool owner_known = std::any_of(providers.begin(), providers.end(), [&](const ProviderIdentity& provider) {
            return provider_equal(provider, value.owning_provider);
        });
        if (!owner_known) return Result<std::vector<ResourceBinding>>::failure({
            "permit_wrong_provider", "resource owner is absent from the bound provider set",
            "$claims.resources[].owning_provider", OutcomeKind::refused});
    }
    std::sort(values.begin(), values.end(), resource_less);
    for (std::size_t index = 1; index < values.size(); ++index) {
        if (resource_key(values[index - 1U]) == resource_key(values[index])) {
            return Result<std::vector<ResourceBinding>>::failure({
                "permit_resource_set_not_closed", "permit resource set contains a duplicate key",
                "$claims.resources", OutcomeKind::refused});
        }
    }
    return Result<std::vector<ResourceBinding>>::success(std::move(values));
}

Result<OperationPermitClaims> canonical_claims(OperationPermitClaims claims)
{
    if (claims.schema != kClaimsSchema ||
        claims.canonicalization_version != kCanonicalizationVersion) {
        return Result<OperationPermitClaims>::failure(
            unsupported("unsupported permit claims or canonicalization version", "$claims.schema"));
    }
    if (!prefixed_hex_id(claims.permit_id, "permit-") ||
        !prefixed_hex_id(claims.issuer_session_id, "session-") ||
        !prefixed_hex_id(claims.nonce, "nonce-")) {
        return Result<OperationPermitClaims>::failure(
            malformed("permit, issuer-session, or nonce identity is invalid"));
    }
    if (!dotted_identifier(claims.operation.kind, 128U) ||
        (claims.operation.launch_intent && !bounded_text(*claims.operation.launch_intent, 64U)) ||
        (claims.operation.isolation_mode && !bounded_text(*claims.operation.isolation_mode, 64U))) {
        return Result<OperationPermitClaims>::failure(
            malformed("operation selection is invalid", "$claims.operation"));
    }
    if (!bounded_text(claims.plan.plan_id, 160U) ||
        !lowercase_hex_digest(claims.plan.plan_digest) ||
        !lowercase_hex_digest(claims.evidence_digest) ||
        !bounded_text(claims.machine_binding_id, 160U)) {
        return Result<OperationPermitClaims>::failure(
            malformed("plan, evidence, or machine binding is invalid"));
    }
    if (!provider_identifier(claims.audience.provider_id) ||
        !bounded_text(claims.audience.provider_revision, 128U) ||
        !provider_identifier(claims.principal.provider_id) ||
        !bounded_text(claims.principal.principal_id, 160U) ||
        !bounded_text(claims.principal.application_session_id, 160U) ||
        !bounded_text(claims.policy.policy_revision, 128U) ||
        !lowercase_hex_digest(claims.policy.policy_digest)) {
        return Result<OperationPermitClaims>::failure(
            malformed("audience, principal, or policy binding is invalid"));
    }
    if (claims.issued_at_unix_seconds > kMaximumExactJsonInteger ||
        claims.not_before_unix_seconds > kMaximumExactJsonInteger ||
        claims.expires_at_unix_seconds > kMaximumExactJsonInteger ||
        claims.issued_at_unix_seconds > claims.not_before_unix_seconds ||
        claims.not_before_unix_seconds >= claims.expires_at_unix_seconds) {
        return Result<OperationPermitClaims>::failure(
            malformed("permit time window is invalid", "$claims.expires_at_unix_seconds"));
    }

    auto effects = canonical_string_set(std::move(claims.effects), true, "$claims.effects");
    if (!effects) return Result<OperationPermitClaims>::failure(effects.error());
    claims.effects = effects.take_value();
    auto capabilities = canonical_string_set(
        std::move(claims.required_capabilities), false, "$claims.required_capabilities");
    if (!capabilities) return Result<OperationPermitClaims>::failure(capabilities.error());
    claims.required_capabilities = capabilities.take_value();
    auto providers = canonical_providers(
        std::move(claims.provider_revisions), "$claims.provider_revisions");
    if (!providers) return Result<OperationPermitClaims>::failure(providers.error());
    claims.provider_revisions = providers.take_value();
    const bool audience_bound = std::any_of(
        claims.provider_revisions.begin(), claims.provider_revisions.end(),
        [&](const ProviderIdentity& value) { return provider_equal(value, claims.audience); });
    if (!audience_bound) return Result<OperationPermitClaims>::failure({
        "permit_wrong_provider", "audience is absent from the bound provider set",
        "$claims.audience", OutcomeKind::refused});
    auto resources = canonical_resources(
        std::move(claims.resources), claims.effects, claims.provider_revisions);
    if (!resources) return Result<OperationPermitClaims>::failure(resources.error());
    claims.resources = resources.take_value();
    return Result<OperationPermitClaims>::success(std::move(claims));
}

json::ObjectBuilder provider_builder(const ProviderIdentity& value)
{
    json::ObjectBuilder output;
    output.add_string("provider_id", value.provider_id);
    output.add_string("provider_revision", value.provider_revision);
    return output;
}

json::ArrayBuilder strings_builder(const std::vector<std::string>& values)
{
    json::ArrayBuilder output;
    for (const std::string& value : values) output.add_string(value);
    return output;
}

json::ObjectBuilder resource_builder(const ResourceBinding& value)
{
    json::ObjectBuilder output;
    output.add_string("resource_kind", value.resource_kind);
    output.add_string("role", value.role);
    output.add_string("logical_id", value.logical_id);
    output.add_string("current_identity_digest", value.current_identity_digest);
    output.add_object("owning_provider", provider_builder(value.owning_provider));
    output.add_array("permitted_effects", strings_builder(value.permitted_effects));
    return output;
}

Result<std::string> encode_canonical_claims(OperationPermitClaims claims)
{
    auto normalized = canonical_claims(std::move(claims));
    if (!normalized) return Result<std::string>::failure(normalized.error());
    const OperationPermitClaims& value = normalized.value();

    json::ObjectBuilder operation;
    operation.add_string("kind", value.operation.kind);
    if (value.operation.launch_intent) operation.add_string("launch_intent", *value.operation.launch_intent);
    else operation.add_null("launch_intent");
    if (value.operation.isolation_mode) operation.add_string("isolation_mode", *value.operation.isolation_mode);
    else operation.add_null("isolation_mode");

    json::ObjectBuilder plan;
    plan.add_string("plan_id", value.plan.plan_id);
    plan.add_string("plan_digest", value.plan.plan_digest);

    json::ObjectBuilder principal;
    principal.add_string("provider_id", value.principal.provider_id);
    principal.add_string("principal_id", value.principal.principal_id);
    principal.add_string("application_session_id", value.principal.application_session_id);

    json::ObjectBuilder policy;
    policy.add_string("policy_revision", value.policy.policy_revision);
    policy.add_string("policy_digest", value.policy.policy_digest);

    json::ArrayBuilder resources;
    for (const ResourceBinding& resource : value.resources) resources.add_object(resource_builder(resource));
    json::ArrayBuilder providers;
    for (const ProviderIdentity& provider : value.provider_revisions) providers.add_object(provider_builder(provider));

    json::ObjectBuilder output;
    output.add_string("schema", value.schema);
    output.add_string("canonicalization_version", value.canonicalization_version);
    output.add_string("permit_id", value.permit_id);
    output.add_string("issuer_session_id", value.issuer_session_id);
    output.add_object("operation", operation);
    output.add_object("plan", plan);
    output.add_object("audience", provider_builder(value.audience));
    output.add_array("resources", resources);
    output.add_array("effects", strings_builder(value.effects));
    output.add_array("required_capabilities", strings_builder(value.required_capabilities));
    output.add_string("machine_binding_id", value.machine_binding_id);
    output.add_object("principal", principal);
    output.add_string("evidence_digest", value.evidence_digest);
    output.add_object("policy", policy);
    output.add_array("provider_revisions", providers);
    (void)output.add_unsigned_integer("issued_at_unix_seconds", value.issued_at_unix_seconds);
    (void)output.add_unsigned_integer("not_before_unix_seconds", value.not_before_unix_seconds);
    (void)output.add_unsigned_integer("expires_at_unix_seconds", value.expires_at_unix_seconds);
    output.add_string("nonce", value.nonce);
    auto parsed = json::parse(output.serialize());
    if (!parsed) return Result<std::string>::failure(malformed(
        "canonical claims could not be encoded", parsed.error().path));
    return Result<std::string>::success(parsed.value().serialize());
}

std::vector<unsigned char> hex_bytes(const std::string& value)
{
    std::vector<unsigned char> output;
    output.reserve(value.size() / 2U);
    auto nibble = [](unsigned char byte) -> unsigned char {
        if (byte >= '0' && byte <= '9') return static_cast<unsigned char>(byte - '0');
        return static_cast<unsigned char>(byte - 'a' + 10U);
    };
    for (std::size_t index = 0; index + 1U < value.size(); index += 2U) {
        output.push_back(static_cast<unsigned char>(
            static_cast<unsigned char>(nibble(static_cast<unsigned char>(value[index])) << 4U) |
            nibble(static_cast<unsigned char>(value[index + 1U]))));
    }
    return output;
}

std::string bytes_hex(const std::vector<unsigned char>& value)
{
    static const char alphabet[] = "0123456789abcdef";
    std::string output;
    output.reserve(value.size() * 2U);
    for (unsigned char byte : value) {
        output.push_back(alphabet[(byte >> 4U) & 0x0fU]);
        output.push_back(alphabet[byte & 0x0fU]);
    }
    return output;
}

void secure_zero(unsigned char* bytes, std::size_t size) noexcept
{
    volatile unsigned char* output = bytes;
    for (std::size_t index = 0; index < size; ++index) output[index] = 0U;
}

bool exact_keys(const json::Value& value, std::initializer_list<const char*> expected)
{
    if (!value.is_object()) return false;
    std::vector<std::string> actual = value.object_keys();
    std::vector<std::string> wanted;
    wanted.reserve(expected.size());
    for (const char* item : expected) wanted.emplace_back(item);
    std::sort(actual.begin(), actual.end());
    std::sort(wanted.begin(), wanted.end());
    return actual == wanted;
}

bool read_string(const json::Value& object, const char* key, std::string& output)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return false;
    auto parsed = value->string_value();
    if (!parsed) return false;
    output = parsed.take_value();
    return true;
}

bool read_optional_string(
    const json::Value& object,
    const char* key,
    std::optional<std::string>& output)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return false;
    if (value->is_null()) {
        output.reset();
        return true;
    }
    auto parsed = value->string_value();
    if (!parsed) return false;
    output = parsed.take_value();
    return true;
}

bool read_unsigned(const json::Value& object, const char* key, std::uint64_t& output)
{
    const json::Value* value = object.find(key);
    if (value == nullptr) return false;
    auto parsed = value->unsigned_integer_value();
    if (!parsed) return false;
    output = parsed.value();
    return true;
}

bool decode_provider(const json::Value& value, ProviderIdentity& output)
{
    return exact_keys(value, {"provider_id", "provider_revision"}) &&
        read_string(value, "provider_id", output.provider_id) &&
        read_string(value, "provider_revision", output.provider_revision);
}

bool decode_string_array(const json::Value& value, std::vector<std::string>& output)
{
    if (!value.is_array()) return false;
    output.clear();
    output.reserve(value.size());
    for (std::size_t index = 0; index < value.size(); ++index) {
        const json::Value* item = value.at(index);
        if (item == nullptr) return false;
        auto text = item->string_value();
        if (!text) return false;
        output.push_back(text.take_value());
    }
    return true;
}

bool decode_resource(const json::Value& value, ResourceBinding& output)
{
    if (!exact_keys(value, {
            "resource_kind", "role", "logical_id", "current_identity_digest",
            "owning_provider", "permitted_effects"})) return false;
    const json::Value* provider = value.find("owning_provider");
    const json::Value* effects = value.find("permitted_effects");
    return read_string(value, "resource_kind", output.resource_kind) &&
        read_string(value, "role", output.role) &&
        read_string(value, "logical_id", output.logical_id) &&
        read_string(value, "current_identity_digest", output.current_identity_digest) &&
        provider != nullptr && decode_provider(*provider, output.owning_provider) &&
        effects != nullptr && decode_string_array(*effects, output.permitted_effects);
}

Result<OperationPermitClaims> decode_claims(const json::Value& value)
{
    if (!exact_keys(value, {
            "schema", "canonicalization_version", "permit_id", "issuer_session_id",
            "operation", "plan", "audience", "resources", "effects",
            "required_capabilities", "machine_binding_id", "principal",
            "evidence_digest", "policy", "provider_revisions",
            "issued_at_unix_seconds", "not_before_unix_seconds",
            "expires_at_unix_seconds", "nonce"})) {
        return Result<OperationPermitClaims>::failure(
            malformed("claims fields are missing or unsupported"));
    }
    OperationPermitClaims claims;
    if (!read_string(value, "schema", claims.schema) ||
        !read_string(value, "canonicalization_version", claims.canonicalization_version) ||
        !read_string(value, "permit_id", claims.permit_id) ||
        !read_string(value, "issuer_session_id", claims.issuer_session_id) ||
        !read_string(value, "machine_binding_id", claims.machine_binding_id) ||
        !read_string(value, "evidence_digest", claims.evidence_digest) ||
        !read_unsigned(value, "issued_at_unix_seconds", claims.issued_at_unix_seconds) ||
        !read_unsigned(value, "not_before_unix_seconds", claims.not_before_unix_seconds) ||
        !read_unsigned(value, "expires_at_unix_seconds", claims.expires_at_unix_seconds) ||
        !read_string(value, "nonce", claims.nonce)) {
        return Result<OperationPermitClaims>::failure(malformed("claims scalar field has the wrong type"));
    }
    if (claims.schema != kClaimsSchema || claims.canonicalization_version != kCanonicalizationVersion) {
        return Result<OperationPermitClaims>::failure(
            unsupported("claims schema or canonicalization version is unsupported", "$claims.schema"));
    }

    const json::Value* operation = value.find("operation");
    const json::Value* plan = value.find("plan");
    const json::Value* audience = value.find("audience");
    const json::Value* resources = value.find("resources");
    const json::Value* effects = value.find("effects");
    const json::Value* capabilities = value.find("required_capabilities");
    const json::Value* principal = value.find("principal");
    const json::Value* policy = value.find("policy");
    const json::Value* providers = value.find("provider_revisions");
    if (operation == nullptr || plan == nullptr || audience == nullptr ||
        resources == nullptr || effects == nullptr || capabilities == nullptr ||
        principal == nullptr || policy == nullptr || providers == nullptr) {
        return Result<OperationPermitClaims>::failure(malformed("claims object field is missing"));
    }
    if (!exact_keys(*operation, {"kind", "launch_intent", "isolation_mode"}) ||
        !read_string(*operation, "kind", claims.operation.kind) ||
        !read_optional_string(*operation, "launch_intent", claims.operation.launch_intent) ||
        !read_optional_string(*operation, "isolation_mode", claims.operation.isolation_mode) ||
        !exact_keys(*plan, {"plan_id", "plan_digest"}) ||
        !read_string(*plan, "plan_id", claims.plan.plan_id) ||
        !read_string(*plan, "plan_digest", claims.plan.plan_digest) ||
        !decode_provider(*audience, claims.audience) ||
        !exact_keys(*principal, {"provider_id", "principal_id", "application_session_id"}) ||
        !read_string(*principal, "provider_id", claims.principal.provider_id) ||
        !read_string(*principal, "principal_id", claims.principal.principal_id) ||
        !read_string(*principal, "application_session_id", claims.principal.application_session_id) ||
        !exact_keys(*policy, {"policy_revision", "policy_digest"}) ||
        !read_string(*policy, "policy_revision", claims.policy.policy_revision) ||
        !read_string(*policy, "policy_digest", claims.policy.policy_digest) ||
        !decode_string_array(*effects, claims.effects) ||
        !decode_string_array(*capabilities, claims.required_capabilities) ||
        !resources->is_array() || !providers->is_array()) {
        return Result<OperationPermitClaims>::failure(malformed("nested claims object is malformed"));
    }
    for (std::size_t index = 0; index < resources->size(); ++index) {
        const json::Value* item = resources->at(index);
        ResourceBinding resource;
        if (item == nullptr || !decode_resource(*item, resource)) {
            return Result<OperationPermitClaims>::failure(malformed("resource binding is malformed"));
        }
        claims.resources.push_back(std::move(resource));
    }
    for (std::size_t index = 0; index < providers->size(); ++index) {
        const json::Value* item = providers->at(index);
        ProviderIdentity provider;
        if (item == nullptr || !decode_provider(*item, provider)) {
            return Result<OperationPermitClaims>::failure(malformed("provider binding is malformed"));
        }
        claims.provider_revisions.push_back(std::move(provider));
    }
    auto normalized = canonical_claims(std::move(claims));
    if (!normalized) return Result<OperationPermitClaims>::failure(normalized.error());
    return normalized;
}

std::string recovery_action(const std::string& code)
{
    if (code == "permit_wrong_plan") return "regenerate_plan";
    if (code == "permit_wrong_evidence" || code == "permit_resource_stale" ||
        code == "permit_wrong_resource" || code == "permit_wrong_provider" ||
        code == "permit_wrong_policy") return "recompute_readiness";
    if (code == "permit_wrong_principal" || code == "permit_authentication_failed") return "reauthenticate";
    if (code == "permit_expired" || code == "permit_replayed" || code == "permit_revoked" ||
        code == "permit_wrong_issuer_session" || code == "permit_not_yet_valid") return "restart_operation";
    if (code == "permit_wrong_operation" || code == "permit_schema_unsupported") return "unsupported_operation";
    return code.empty() ? "none" : "review_again";
}

PermitOutcome refusal(
    const std::string& code,
    const OperationPermitEnvelope& envelope,
    const PermitValidationContext& expected)
{
    PermitOutcome output;
    output.code = code;
    output.permit_id = envelope.claims.permit_id;
    output.claims_digest = envelope.claims_digest;
    output.consumer_provider_id = expected.consumer.provider_id;
    output.recovery_action = recovery_action(code);
    return output;
}

PermitOutcome acceptance(
    const OperationPermitEnvelope& envelope,
    const PermitValidationContext& expected,
    bool consumed)
{
    PermitOutcome output;
    output.accepted = true;
    output.consumed = consumed;
    output.permit_id = envelope.claims.permit_id;
    output.claims_digest = envelope.claims_digest;
    output.consumer_provider_id = expected.consumer.provider_id;
    return output;
}

bool providers_equal(
    std::vector<ProviderIdentity> left,
    std::vector<ProviderIdentity> right)
{
    std::sort(left.begin(), left.end(), provider_less);
    std::sort(right.begin(), right.end(), provider_less);
    if (left.size() != right.size()) return false;
    for (std::size_t index = 0; index < left.size(); ++index) {
        if (!provider_equal(left[index], right[index])) return false;
    }
    return true;
}

std::string compare_resources(
    std::vector<ResourceBinding> actual,
    std::vector<ResourceBinding> expected)
{
    std::sort(actual.begin(), actual.end(), resource_less);
    std::sort(expected.begin(), expected.end(), resource_less);
    if (actual.size() != expected.size()) return "permit_wrong_resource";
    for (std::size_t index = 0; index < actual.size(); ++index) {
        if (resource_key(actual[index]) != resource_key(expected[index])) return "permit_wrong_resource";
        if (!provider_equal(actual[index].owning_provider, expected[index].owning_provider)) {
            return "permit_wrong_provider";
        }
        if (actual[index].permitted_effects != expected[index].permitted_effects) {
            return "permit_wrong_resource";
        }
        if (actual[index].current_identity_digest != expected[index].current_identity_digest) {
            return "permit_resource_stale";
        }
    }
    return {};
}

} // namespace

struct PermitLedger::Impl {
    struct Record {
        std::string permit_id;
        std::string nonce;
        std::string claims_digest;
        std::string issuer_session_id;
        std::string audience_provider_id;
        PermitLedgerState state = PermitLedgerState::issued;
        std::uint64_t issued_monotonic_milliseconds = 0;
        std::uint64_t deadline_monotonic_milliseconds = 0;
    };

    static std::string key(const std::string& permit_id, const std::string& nonce)
    {
        return permit_id + "\n" + nonce;
    }

    mutable std::mutex mutex;
    std::map<std::string, Record> records;
};

PermitOutcome PermitValidator::validate_common(
    const OperationPermitEnvelope& envelope,
    const PermitValidationContext& expected,
    const PermitAuthenticator& authenticator,
    const PermitLedger& ledger,
    const PermitClock& clock) const
{
    if (envelope.schema != kEnvelopeSchema || envelope.claims.schema != kClaimsSchema ||
        envelope.claims.canonicalization_version != kCanonicalizationVersion) {
        return refusal("permit_schema_unsupported", envelope, expected);
    }
    auto canonical = encode_canonical_claims(envelope.claims);
    if (!canonical) return refusal(canonical.error().code, envelope, expected);
    if (envelope.authenticator_algorithm != kProcessHmacAlgorithm ||
        authenticator.algorithm() != kProcessHmacAlgorithm) {
        return refusal("permit_schema_unsupported", envelope, expected);
    }
    if (envelope.claims.issuer_session_id != authenticator.issuer_session_id()) {
        return refusal("permit_wrong_issuer_session", envelope, expected);
    }
    const std::string actual_digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(canonical.value().data()), canonical.value().size());
    if (!constant_time_equal(actual_digest, envelope.claims_digest) ||
        !authenticator.verify(canonical.value(), envelope.authenticator_value)) {
        return refusal("permit_authentication_failed", envelope, expected);
    }

    const std::uint64_t now = clock.unix_seconds();
    const OperationPermitClaims& claims = envelope.claims;
    if (claims.expires_at_unix_seconds <= claims.issued_at_unix_seconds ||
        claims.expires_at_unix_seconds - claims.issued_at_unix_seconds > policy_.maximum_ttl_seconds) {
        return refusal("permit_lifetime_exceeded", envelope, expected);
    }
    if (claims.issued_at_unix_seconds > now &&
        claims.issued_at_unix_seconds - now > policy_.maximum_future_skew_seconds) {
        return refusal("permit_lifetime_exceeded", envelope, expected);
    }
    if (now < claims.not_before_unix_seconds) return refusal("permit_not_yet_valid", envelope, expected);
    if (now >= claims.expires_at_unix_seconds) return refusal("permit_expired", envelope, expected);

    {
        std::lock_guard<std::mutex> guard(ledger.impl_->mutex);
        const auto found = ledger.impl_->records.find(PermitLedger::Impl::key(
            envelope.claims.permit_id, envelope.claims.nonce));
        if (found == ledger.impl_->records.end()) return refusal(
            "permit_wrong_issuer_session", envelope, expected);
        const PermitLedger::Impl::Record& record = found->second;
        if (record.claims_digest != envelope.claims_digest) return refusal(
            "permit_authentication_failed", envelope, expected);
        if (record.issuer_session_id != envelope.claims.issuer_session_id) return refusal(
            "permit_wrong_issuer_session", envelope, expected);
        if (record.audience_provider_id != envelope.claims.audience.provider_id) return refusal(
            "permit_wrong_audience", envelope, expected);
        if (record.state == PermitLedgerState::revoked) return refusal(
            "permit_revoked", envelope, expected);
        if (record.state == PermitLedgerState::consumed) return refusal(
            "permit_replayed", envelope, expected);
        const std::uint64_t monotonic_now = clock.monotonic_milliseconds();
        if (monotonic_now < record.issued_monotonic_milliseconds ||
            monotonic_now >= record.deadline_monotonic_milliseconds) return refusal(
                "permit_expired", envelope, expected);
    }

    if (claims.operation.kind != expected.operation.kind) {
        return refusal("permit_wrong_operation", envelope, expected);
    }
    if (claims.operation.launch_intent != expected.operation.launch_intent) {
        return refusal("permit_intent_mismatch", envelope, expected);
    }
    if (claims.operation.isolation_mode != expected.operation.isolation_mode) {
        return refusal("permit_isolation_mismatch", envelope, expected);
    }
    if (!provider_equal(claims.audience, expected.consumer)) {
        return refusal("permit_wrong_audience", envelope, expected);
    }
    if (!plan_equal(claims.plan, expected.plan)) return refusal("permit_wrong_plan", envelope, expected);
    if (claims.machine_binding_id != expected.machine_binding_id) {
        return refusal("permit_wrong_machine", envelope, expected);
    }
    if (!principal_equal(claims.principal, expected.principal)) {
        return refusal("permit_wrong_principal", envelope, expected);
    }
    if (claims.evidence_digest != expected.evidence_digest) {
        return refusal("permit_wrong_evidence", envelope, expected);
    }
    if (!policy_equal(claims.policy, expected.policy)) {
        return refusal("permit_wrong_policy", envelope, expected);
    }
    if (!providers_equal(claims.provider_revisions, expected.provider_revisions)) {
        return refusal("permit_wrong_provider", envelope, expected);
    }

    auto expected_effects = canonical_string_set(expected.effects, true, "$expected.effects");
    if (!expected_effects) return refusal("permit_effect_scope_mismatch", envelope, expected);
    if (claims.effects != expected_effects.value()) {
        return refusal("permit_effect_scope_mismatch", envelope, expected);
    }
    auto expected_capabilities = canonical_string_set(
        expected.required_capabilities, false, "$expected.required_capabilities");
    if (!expected_capabilities) return refusal("permit_capability_scope_mismatch", envelope, expected);
    if (claims.required_capabilities != expected_capabilities.value()) {
        return refusal("permit_capability_scope_mismatch", envelope, expected);
    }
    auto expected_providers = canonical_providers(expected.provider_revisions, "$expected.provider_revisions");
    if (!expected_providers) return refusal("permit_wrong_provider", envelope, expected);
    auto expected_resources = canonical_resources(
        expected.resources, expected_effects.value(), expected_providers.value());
    if (!expected_resources) return refusal("permit_resource_set_not_closed", envelope, expected);
    const std::string resource_problem = compare_resources(claims.resources, expected_resources.value());
    if (!resource_problem.empty()) return refusal(resource_problem, envelope, expected);
    return acceptance(envelope, expected, false);
}

std::uint64_t SystemPermitClock::unix_seconds() const
{
    const auto value = std::chrono::duration_cast<std::chrono::seconds>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    return value < 0 ? 0U : static_cast<std::uint64_t>(value);
}

std::uint64_t SystemPermitClock::monotonic_milliseconds() const
{
    const auto value = std::chrono::duration_cast<std::chrono::milliseconds>(
        std::chrono::steady_clock::now().time_since_epoch()).count();
    return value < 0 ? 0U : static_cast<std::uint64_t>(value);
}

ProcessSessionAuthenticator::ProcessSessionAuthenticator(
    std::string session_id,
    std::vector<unsigned char> key)
    : session_id_(std::move(session_id)), key_(std::move(key)) {}

Result<std::unique_ptr<ProcessSessionAuthenticator>> ProcessSessionAuthenticator::create(
    PermitEntropySource& entropy)
{
    std::vector<unsigned char> key(32U);
    std::vector<unsigned char> session(16U);
    auto key_result = entropy.fill(key.data(), key.size());
    auto session_result = key_result ? entropy.fill(session.data(), session.size())
                                     : Result<void>::failure(key_result.error());
    if (!key_result || !session_result) {
        secure_zero(key.data(), key.size());
        secure_zero(session.data(), session.size());
        return Result<std::unique_ptr<ProcessSessionAuthenticator>>::failure({
            "permit_authentication_failed", "a cryptographically secure process entropy source is unavailable",
            "$authenticator", OutcomeKind::unavailable});
    }
    const std::string session_id = "session-" + bytes_hex(session);
    secure_zero(session.data(), session.size());
    return Result<std::unique_ptr<ProcessSessionAuthenticator>>::success(
        std::unique_ptr<ProcessSessionAuthenticator>(
            new ProcessSessionAuthenticator(session_id, std::move(key))));
}

ProcessSessionAuthenticator::~ProcessSessionAuthenticator()
{
    if (!key_.empty()) secure_zero(key_.data(), key_.size());
}

ProcessSessionAuthenticator::ProcessSessionAuthenticator(ProcessSessionAuthenticator&& other) noexcept
    : session_id_(std::move(other.session_id_)), key_(std::move(other.key_)) {}
ProcessSessionAuthenticator& ProcessSessionAuthenticator::operator=(ProcessSessionAuthenticator&& other) noexcept
{
    if (this != &other) {
        if (!key_.empty()) secure_zero(key_.data(), key_.size());
        session_id_ = std::move(other.session_id_);
        key_ = std::move(other.key_);
    }
    return *this;
}

std::string ProcessSessionAuthenticator::algorithm() const { return kProcessHmacAlgorithm; }
std::string ProcessSessionAuthenticator::issuer_session_id() const { return session_id_; }
std::string ProcessSessionAuthenticator::authenticate(const std::string& canonical_claims) const
{
    return hmac_sha256_hex(key_, canonical_claims);
}
bool ProcessSessionAuthenticator::verify(
    const std::string& canonical_claims,
    const std::string& authenticator_value) const
{
    return constant_time_equal(authenticate(canonical_claims), authenticator_value);
}

PermitLedger::PermitLedger() : impl_(std::make_unique<Impl>()) {}
PermitLedger::~PermitLedger() = default;
PermitLedger::PermitLedger(PermitLedger&&) noexcept = default;
PermitLedger& PermitLedger::operator=(PermitLedger&&) noexcept = default;

Result<void> PermitLedger::register_issued(
    const OperationPermitEnvelope& envelope,
    std::uint64_t issued_monotonic_milliseconds,
    std::uint64_t deadline_monotonic_milliseconds)
{
    if (!prefixed_hex_id(envelope.claims.permit_id, "permit-") ||
        !prefixed_hex_id(envelope.claims.nonce, "nonce-") ||
        !lowercase_hex_digest(envelope.claims_digest) ||
        deadline_monotonic_milliseconds <= issued_monotonic_milliseconds) {
        return Result<void>::failure(malformed("issued permit ledger record is invalid", "$ledger"));
    }
    Impl::Record record;
    record.permit_id = envelope.claims.permit_id;
    record.nonce = envelope.claims.nonce;
    record.claims_digest = envelope.claims_digest;
    record.issuer_session_id = envelope.claims.issuer_session_id;
    record.audience_provider_id = envelope.claims.audience.provider_id;
    record.issued_monotonic_milliseconds = issued_monotonic_milliseconds;
    record.deadline_monotonic_milliseconds = deadline_monotonic_milliseconds;
    std::lock_guard<std::mutex> guard(impl_->mutex);
    if (impl_->records.size() >= 4096U) return Result<void>::failure({
        "permit_lifetime_exceeded", "process permit ledger reached its bounded capacity",
        "$ledger", OutcomeKind::unavailable});
    for (const auto& item : impl_->records) {
        if (item.second.permit_id == record.permit_id || item.second.nonce == record.nonce) {
            return Result<void>::failure({
                "permit_replayed", "permit ID or nonce is already registered",
                "$ledger", OutcomeKind::conflict});
        }
    }
    const auto inserted = impl_->records.emplace(
        Impl::key(record.permit_id, record.nonce), std::move(record));
    if (!inserted.second) return Result<void>::failure({
        "permit_replayed", "permit ID and nonce are already registered",
        "$ledger", OutcomeKind::conflict});
    return Result<void>::success();
}

Result<void> PermitLedger::revoke(
    const std::string& permit_id,
    const std::string& nonce,
    const std::string& claims_digest)
{
    std::lock_guard<std::mutex> guard(impl_->mutex);
    const auto found = impl_->records.find(Impl::key(permit_id, nonce));
    if (found == impl_->records.end() || found->second.claims_digest != claims_digest) {
        return Result<void>::failure({
            "permit_wrong_issuer_session", "permit is not present in the current issuer ledger",
            "$ledger", OutcomeKind::not_found});
    }
    if (found->second.state == PermitLedgerState::consumed) return Result<void>::failure({
        "permit_replayed", "consumed permit cannot be revoked",
        "$ledger", OutcomeKind::conflict});
    found->second.state = PermitLedgerState::revoked;
    return Result<void>::success();
}

PermitValidator::PermitValidator(PermitTimePolicy policy) : policy_(policy) {}

PermitOutcome PermitValidator::validate(
    const OperationPermitEnvelope& envelope,
    const PermitValidationContext& expected,
    const PermitAuthenticator& authenticator,
    const PermitLedger& ledger,
    const PermitClock& clock) const
{
    return validate_common(envelope, expected, authenticator, ledger, clock);
}

PermitOutcome PermitValidator::consume(
    const OperationPermitEnvelope& envelope,
    const PermitValidationContext& expected,
    const PermitAuthenticator& authenticator,
    PermitLedger& ledger,
    const PermitClock& clock) const
{
    PermitOutcome checked = validate_common(
        envelope, expected, authenticator, ledger, clock);
    if (!checked.accepted) return checked;
    std::lock_guard<std::mutex> guard(ledger.impl_->mutex);
    const auto found = ledger.impl_->records.find(PermitLedger::Impl::key(
        envelope.claims.permit_id, envelope.claims.nonce));
    if (found == ledger.impl_->records.end()) return refusal(
        "permit_wrong_issuer_session", envelope, expected);
    PermitLedger::Impl::Record& record = found->second;
    if (record.claims_digest != envelope.claims_digest) return refusal(
        "permit_authentication_failed", envelope, expected);
    if (record.state == PermitLedgerState::revoked) return refusal(
        "permit_revoked", envelope, expected);
    if (record.state == PermitLedgerState::consumed) return refusal(
        "permit_replayed", envelope, expected);
    const std::uint64_t monotonic_now = clock.monotonic_milliseconds();
    if (monotonic_now < record.issued_monotonic_milliseconds ||
        monotonic_now >= record.deadline_monotonic_milliseconds) {
        return refusal("permit_expired", envelope, expected);
    }
    record.state = PermitLedgerState::consumed;
    return acceptance(envelope, expected, true);
}

Result<std::string> canonical_claims_json(const OperationPermitClaims& claims)
{
    return encode_canonical_claims(claims);
}

Result<OperationPermitEnvelope> seal_claims(
    const OperationPermitClaims& claims,
    const PermitAuthenticator& authenticator)
{
    if (claims.issuer_session_id != authenticator.issuer_session_id()) {
        return Result<OperationPermitEnvelope>::failure({
            "permit_wrong_issuer_session", "claims do not belong to the active authenticator session",
            "$claims.issuer_session_id", OutcomeKind::refused});
    }
    if (authenticator.algorithm() != kProcessHmacAlgorithm) {
        return Result<OperationPermitEnvelope>::failure(
            unsupported("authenticator algorithm is unsupported", "$authenticator.algorithm"));
    }
    auto normalized = canonical_claims(claims);
    if (!normalized) return Result<OperationPermitEnvelope>::failure(normalized.error());
    auto canonical = canonical_claims_json(normalized.value());
    if (!canonical) return Result<OperationPermitEnvelope>::failure(canonical.error());
    OperationPermitEnvelope envelope;
    envelope.claims = normalized.take_value();
    envelope.claims_digest = facman::base::sha256_hex_bytes(
        reinterpret_cast<const unsigned char*>(canonical.value().data()), canonical.value().size());
    envelope.authenticator_value = authenticator.authenticate(canonical.value());
    if (!lowercase_hex_digest(envelope.authenticator_value)) {
        return Result<OperationPermitEnvelope>::failure({
            "permit_authentication_failed", "authenticator returned a non-SHA-256 value",
            "$authenticator.value", OutcomeKind::internal_error});
    }
    return Result<OperationPermitEnvelope>::success(std::move(envelope));
}

Result<std::string> envelope_json(const OperationPermitEnvelope& envelope)
{
    auto claims = canonical_claims_json(envelope.claims);
    if (!claims) return Result<std::string>::failure(claims.error());
    auto parsed_claims = json::parse(claims.value());
    if (!parsed_claims) return Result<std::string>::failure(malformed("claims serialization failed"));
    json::ObjectBuilder authenticator;
    authenticator.add_string("algorithm", envelope.authenticator_algorithm);
    authenticator.add_string("value", envelope.authenticator_value);
    json::ObjectBuilder output;
    output.add_string("schema", envelope.schema);
    output.add_value("claims", parsed_claims.value());
    output.add_string("claims_digest", envelope.claims_digest);
    output.add_object("authenticator", authenticator);
    return Result<std::string>::success(output.serialize());
}

Result<OperationPermitEnvelope> decode_envelope(const std::string& text)
{
    json::Limits limits;
    limits.maximum_bytes = 1024U * 1024U;
    limits.maximum_depth = 32U;
    limits.maximum_nodes = 4096U;
    limits.maximum_string_bytes = 65536U;
    auto document = json::parse(text, limits);
    if (!document) return Result<OperationPermitEnvelope>::failure({
        "permit_malformed", document.error().message, document.error().path,
        OutcomeKind::invalid_argument});
    if (!exact_keys(document.value(), {"schema", "claims", "claims_digest", "authenticator"})) {
        return Result<OperationPermitEnvelope>::failure(
            malformed("permit envelope fields are missing or unsupported", "$"));
    }
    OperationPermitEnvelope envelope;
    if (!read_string(document.value(), "schema", envelope.schema)) {
        return Result<OperationPermitEnvelope>::failure(malformed("permit envelope schema is missing", "$.schema"));
    }
    if (envelope.schema != kEnvelopeSchema) return Result<OperationPermitEnvelope>::failure(
        unsupported("permit envelope schema is unsupported", "$.schema"));
    const json::Value* claims = document.value().find("claims");
    const json::Value* authenticator = document.value().find("authenticator");
    if (claims == nullptr || authenticator == nullptr ||
        !read_string(document.value(), "claims_digest", envelope.claims_digest) ||
        !lowercase_hex_digest(envelope.claims_digest) ||
        !exact_keys(*authenticator, {"algorithm", "value"}) ||
        !read_string(*authenticator, "algorithm", envelope.authenticator_algorithm) ||
        !read_string(*authenticator, "value", envelope.authenticator_value) ||
        !lowercase_hex_digest(envelope.authenticator_value)) {
        return Result<OperationPermitEnvelope>::failure(malformed("permit envelope authenticator is malformed"));
    }
    if (envelope.authenticator_algorithm != kProcessHmacAlgorithm) {
        return Result<OperationPermitEnvelope>::failure(
            unsupported("permit authenticator algorithm is unsupported", "$.authenticator.algorithm"));
    }
    auto decoded_claims = decode_claims(*claims);
    if (!decoded_claims) return Result<OperationPermitEnvelope>::failure(decoded_claims.error());
    envelope.claims = decoded_claims.take_value();
    return Result<OperationPermitEnvelope>::success(std::move(envelope));
}

std::string hmac_sha256_hex(
    const std::vector<unsigned char>& key,
    const std::string& message)
{
    constexpr std::size_t block_size = 64U;
    std::vector<unsigned char> effective_key = key;
    if (effective_key.size() > block_size) {
        effective_key = hex_bytes(facman::base::sha256_hex_bytes(effective_key));
    }
    effective_key.resize(block_size, 0U);
    std::array<unsigned char, block_size> inner_pad{};
    std::array<unsigned char, block_size> outer_pad{};
    for (std::size_t index = 0; index < block_size; ++index) {
        inner_pad[index] = static_cast<unsigned char>(effective_key[index] ^ 0x36U);
        outer_pad[index] = static_cast<unsigned char>(effective_key[index] ^ 0x5cU);
    }
    facman::base::Sha256Hasher inner;
    inner.update(inner_pad.data(), inner_pad.size());
    inner.update(reinterpret_cast<const unsigned char*>(message.data()), message.size());
    std::vector<unsigned char> inner_digest = hex_bytes(inner.finish());
    facman::base::Sha256Hasher outer;
    outer.update(outer_pad.data(), outer_pad.size());
    outer.update(inner_digest.data(), inner_digest.size());
    const std::string result = outer.finish();
    secure_zero(effective_key.data(), effective_key.size());
    secure_zero(inner_pad.data(), inner_pad.size());
    secure_zero(outer_pad.data(), outer_pad.size());
    if (!inner_digest.empty()) secure_zero(inner_digest.data(), inner_digest.size());
    return result;
}

bool constant_time_equal(const std::string& left, const std::string& right) noexcept
{
    const std::size_t maximum = std::max(left.size(), right.size());
    std::size_t difference = left.size() ^ right.size();
    for (std::size_t index = 0; index < maximum; ++index) {
        const unsigned char a = index < left.size() ? static_cast<unsigned char>(left[index]) : 0U;
        const unsigned char b = index < right.size() ? static_cast<unsigned char>(right[index]) : 0U;
        difference |= static_cast<std::size_t>(a ^ b);
    }
    return difference == 0U;
}

std::string PermitOutcome::validation_json() const
{
    json::ObjectBuilder output;
    output.add_string("schema", "common.permit_validation_result.v1");
    output.add_string("status", accepted ? "accepted" : "refused");
    if (code.empty()) output.add_null("code");
    else output.add_string("code", code);
    if (permit_id.empty()) output.add_null("permit_id");
    else output.add_string("permit_id", permit_id);
    if (claims_digest.empty()) output.add_null("claims_digest");
    else output.add_string("claims_digest", claims_digest);
    output.add_string("consumer_provider_id", consumer_provider_id);
    output.add_bool("consumed", false);
    output.add_string("recovery_action", recovery_action);
    return output.serialize();
}

std::string PermitOutcome::consumption_json() const
{
    json::ObjectBuilder output;
    output.add_string("schema", "common.permit_consumption_result.v1");
    output.add_string("status", accepted && consumed ? "consumed" : "refused");
    if (code.empty()) output.add_null("code");
    else output.add_string("code", code);
    if (permit_id.empty()) output.add_null("permit_id");
    else output.add_string("permit_id", permit_id);
    if (claims_digest.empty()) output.add_null("claims_digest");
    else output.add_string("claims_digest", claims_digest);
    output.add_string("consumer_provider_id", consumer_provider_id);
    output.add_bool("consumed", accepted && consumed);
    output.add_string("recovery_action", recovery_action);
    return output.serialize();
}

} // namespace facman::core::permit
