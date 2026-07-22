// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#ifndef FLB_FACTORIO_HERMETIC_CANDIDATE_H
#define FLB_FACTORIO_HERMETIC_CANDIDATE_H

#include "fl_operation_permit.h"
#include "fl_process_supervisor.h"
#include "fl_result.h"
#include "flb_factorio_execution.h"

#include <cstddef>
#include <cstdint>
#include <filesystem>
#include <functional>
#include <string>
#include <vector>

namespace facman::factorio::launch {

inline constexpr const char* kHermeticCandidatePolicyId =
    "facman.hermetic-standalone-play.2.0.77.windows-x64.v1";
inline constexpr const char* kHermeticCandidatePolicyRevision = "1";
inline constexpr const char* kHermeticCandidatePolicyDigest =
    "6fde31f26d57e23d67c01dd598cb869a4914d11711868b46d4f817709455e7a2";
inline constexpr const char* kHermeticCandidateOperation = "instance.play";
inline constexpr const char* kHermeticCandidateIntent = "menu";
inline constexpr const char* kHermeticCandidateIsolation = "hermetic";
inline constexpr const char* kHermeticCandidateProviderId = "factorio.launch.local";
inline constexpr const char* kHermeticCandidateProviderRevision =
    "hermetic-standalone-play-candidate.v1";
inline constexpr const char* kHermeticObservationProviderId =
    "factorio.play.process-tree-observer";
inline constexpr const char* kHermeticObservationProviderRevision =
    "bound-observation-artifact.v1";

std::vector<std::string> hermetic_policy_writable_resource_ids();
std::vector<std::string> hermetic_policy_protected_resource_ids();
std::vector<std::string> hermetic_candidate_automated_controls();

struct FrozenHermeticPlayPolicy {
    std::string policy_id;
    std::string policy_revision;
    std::string policy_digest;
    std::string canonicalization_version;
    bool verified = false;

    static facman::core::Result<FrozenHermeticPlayPolicy> verify_canonical_document(
        const std::string& canonical_policy_json);
};

struct HermeticCandidateSelector {
    std::string platform;
    std::string architecture;
    std::string factorio_version;
    std::string distribution;
    std::string source_authentication;
    std::string filesystem;
    std::string volume;
    std::string instance_ownership;
    std::string mod_state;
    std::string account_requirement;
    std::string credential_requirement;
    std::string network_requirement;
};

struct CandidateEvidenceBinding {
    std::string requirement_id;
    std::string identity_digest;
};

struct CandidatePlanInput {
    FrozenHermeticPlayPolicy policy;
    HermeticCandidateSelector selector;
    std::string instance_id;
    std::string machine_binding_id;
    facman::core::permit::PrincipalIdentity principal;
    std::vector<CandidateEvidenceBinding> evidence;
    std::vector<facman::core::permit::ResourceBinding> permit_resources;
    std::vector<facman::core::permit::ProviderIdentity> provider_revisions;
    std::vector<std::string> writable_resource_ids;
    std::vector<std::string> protected_resource_ids;
    facman::platform::ProcessRequest process;
    std::string environment_revision;
};

struct HermeticCandidatePlan {
    std::string schema = "factorio.hermetic_play_candidate_plan.v1";
    std::string canonicalization_version = "facman.sorted-json.v1";
    FrozenHermeticPlayPolicy policy;
    HermeticCandidateSelector selector;
    std::string instance_id;
    std::string machine_binding_id;
    facman::core::permit::PrincipalIdentity principal;
    std::vector<CandidateEvidenceBinding> evidence;
    std::string evidence_digest;
    std::vector<facman::core::permit::ResourceBinding> permit_resources;
    std::vector<facman::core::permit::ProviderIdentity> provider_revisions;
    std::vector<std::string> writable_resource_ids;
    std::vector<std::string> protected_resource_ids;
    facman::platform::ProcessRequest process;
    std::string environment_revision;
    std::string plan_id;
    std::string plan_digest;
};

facman::core::Result<HermeticCandidatePlan> build_hermetic_candidate_plan(
    CandidatePlanInput input);

std::string hermetic_candidate_plan_json(const HermeticCandidatePlan& plan);

facman::core::permit::PermitValidationContext candidate_permit_context(
    const HermeticCandidatePlan& plan);

class PlatformPermitEntropySource final : public facman::core::permit::PermitEntropySource {
public:
    facman::core::Result<void> fill(
        unsigned char* output,
        std::size_t size) noexcept override;
};

class CandidatePermitIssuer {
public:
    explicit CandidatePermitIssuer(std::uint64_t ttl_seconds = 30U);

    facman::core::Result<facman::core::permit::OperationPermitEnvelope> issue(
        const HermeticCandidatePlan& plan,
        const facman::core::permit::PermitAuthenticator& authenticator,
        facman::core::permit::PermitEntropySource& entropy,
        facman::core::permit::PermitLedger& ledger,
        const facman::core::permit::PermitClock& clock) const;

    static bool public_issuance_available() noexcept { return false; }

private:
    std::uint64_t ttl_seconds_;
};

struct ObservationGapState {
    bool lost_events = false;
    bool buffer_overflow = false;
    bool unknown_process_identity = false;
    bool unresolved_target = false;
    bool delayed_events = false;
    bool attribution_gap = false;
    bool provider_failure = false;

    bool any() const noexcept;
};

struct CandidateObservedEffect {
    std::uint64_t sequence = 0;
    std::string domain;
    std::string process_identity_digest;
    std::string target_identity_digest;
    std::string logical_resource_id;
    std::string classification;
};

struct CandidateObservationResult {
    std::string provider_id = kHermeticObservationProviderId;
    std::string provider_revision = kHermeticObservationProviderRevision;
    std::string plan_digest;
    std::string capture_session_digest;
    std::string raw_artifact_digest;
    bool active_before_process = false;
    bool capture_complete = false;
    ObservationGapState gaps;
    std::vector<CandidateObservedEffect> effects;
    std::string output_digest;
};

std::string candidate_observation_artifact_json(
    const CandidateObservationResult& observation);

facman::core::Result<CandidateObservationResult> decode_candidate_observation_artifact(
    const std::string& text,
    const HermeticCandidatePlan& plan,
    const facman::platform::ProcessResult& process);

facman::core::Result<CandidateObservationResult>
read_candidate_observation_artifact_no_follow(
    const std::filesystem::path& path,
    const HermeticCandidatePlan& plan,
    const facman::platform::ProcessResult& process,
    std::size_t maximum_bytes = 64U * 1024U * 1024U);

class CandidateEffectObserver {
public:
    virtual ~CandidateEffectObserver() = default;
    virtual facman::core::Result<void> begin(
        const HermeticCandidatePlan& plan) = 0;
    virtual bool active() const noexcept = 0;
    virtual CandidateObservationResult finish(
        const HermeticCandidatePlan& plan,
        const facman::platform::ProcessResult& process) = 0;
};

using CandidateObservationStart = std::function<facman::core::Result<std::string>(
    const HermeticCandidatePlan& plan)>;
using CandidateObservationFinish = std::function<facman::core::Result<std::filesystem::path>(
    const HermeticCandidatePlan& plan,
    const facman::platform::ProcessResult& process)>;

class BoundArtifactCandidateEffectObserver final : public CandidateEffectObserver {
public:
    BoundArtifactCandidateEffectObserver(
        CandidateObservationStart start_capture,
        CandidateObservationFinish finish_capture,
        std::size_t maximum_artifact_bytes = 64U * 1024U * 1024U);

    facman::core::Result<void> begin(
        const HermeticCandidatePlan& plan) override;
    bool active() const noexcept override;
    CandidateObservationResult finish(
        const HermeticCandidatePlan& plan,
        const facman::platform::ProcessResult& process) override;

private:
    CandidateObservationStart start_capture_;
    CandidateObservationFinish finish_capture_;
    std::size_t maximum_artifact_bytes_;
    std::string plan_digest_;
    std::string capture_session_digest_;
    bool active_ = false;
};

struct ProtectedResourceComparison {
    std::string resource_id;
    std::string before_digest;
    std::string after_digest;
    bool complete = false;
    bool changed = false;
};

struct ProtectedComparisonResult {
    std::string provider_id = "factorio.play.protected-comparison";
    std::string provider_revision = "stable-protected-comparison.v1";
    bool complete = false;
    std::vector<ProtectedResourceComparison> resources;
    std::string output_digest;
};

struct CandidateExecutionRecord {
    facman::core::permit::PermitOutcome permit;
    facman::platform::ProcessResult process;
    CandidateObservationResult observation;
    bool process_creation_requested = false;
};

using CandidateCurrentContext = std::function<
    facman::core::Result<facman::core::permit::PermitValidationContext>()>;

class HermeticCandidateLaunchProvider {
public:
    facman::core::Result<CandidateExecutionRecord> consume_and_execute(
        const facman::core::permit::OperationPermitEnvelope& envelope,
        const HermeticCandidatePlan& reviewed_plan,
        const CandidateCurrentContext& observe_current,
        const facman::core::permit::PermitAuthenticator& authenticator,
        facman::core::permit::PermitLedger& ledger,
        const facman::core::permit::PermitClock& clock,
        CandidateEffectObserver& observer,
        ProcessSupervisor& supervisor) const;

    static bool public_execution_available() noexcept { return false; }

private:
    facman::core::permit::PermitValidator validator_;
};

struct CandidateOutputRecord {
    std::size_t standard_output_bytes = 0;
    std::size_t standard_error_bytes = 0;
    std::string standard_output_digest;
    std::string standard_error_digest;
    std::string combined_digest;
};

CandidateOutputRecord candidate_output_record(
    const facman::platform::ProcessResult& process);

enum class CandidateTechnicalDisposition {
    refused_before_process,
    fail_evidence,
    inconclusive,
    eligible_for_human_verdict,
};

const char* candidate_technical_disposition_name(
    CandidateTechnicalDisposition value) noexcept;

struct CandidateAutomatedCaseResult {
    std::string case_id;
    bool passed = false;
};

struct PlayCandidateEvidencePacket {
    std::string schema = "factorio.play_candidate_evidence_packet.v1";
    std::string canonicalization_version = "facman.sorted-json.v1";
    CandidateTechnicalDisposition technical_disposition =
        CandidateTechnicalDisposition::inconclusive;
    std::string policy_digest;
    std::string plan_id;
    std::string plan_digest;
    std::string evidence_digest;
    std::string permit_id;
    std::string permit_claims_digest;
    bool permit_consumed = false;
    std::string process_identity_digest;
    std::string process_termination;
    CandidateObservationResult observation;
    ProtectedComparisonResult protected_comparison;
    CandidateOutputRecord process_output;
    std::vector<CandidateAutomatedCaseResult> automated_cases;
    std::string human_verdict = "unset";
    bool grants_authority = false;
    bool product_route_available = false;
    std::string packet_digest;

    std::string canonical_json() const;
};

facman::core::Result<PlayCandidateEvidencePacket> build_candidate_evidence_packet(
    const HermeticCandidatePlan& plan,
    const CandidateExecutionRecord& execution,
    ProtectedComparisonResult protected_comparison,
    std::vector<CandidateAutomatedCaseResult> automated_cases);

struct CandidateArtifactRecord {
    std::filesystem::path operation_directory;
    std::filesystem::path lifecycle_packet_path;
    std::filesystem::path standard_output_path;
    std::filesystem::path standard_error_path;
    CandidateOutputRecord process_output;
};

facman::core::Result<CandidateArtifactRecord> persist_candidate_artifacts(
    const std::filesystem::path& workspace,
    const std::string& operation_id,
    const PlayCandidateEvidencePacket& packet,
    const facman::platform::ProcessResult& process);

facman::core::Result<std::string> read_candidate_lifecycle_packet_no_follow(
    const std::filesystem::path& path,
    const std::string& expected_packet_digest,
    std::size_t maximum_bytes = 4U * 1024U * 1024U);

} // namespace facman::factorio::launch

#endif
