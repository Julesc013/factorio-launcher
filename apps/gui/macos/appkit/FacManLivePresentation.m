// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import "FacManLivePresentation.h"
#import "CommandClient.h"

static NSDictionary *FacManPayload(FacManCommandResult *result);
static NSString *FacManText(NSDictionary *record, NSString *key);
static NSArray *FacManArray(NSDictionary *record, NSString *key);

@interface FacManLivePresentation ()
@property(nonatomic, strong) FacManCommandClient *client;
@property(nonatomic, strong) NSDictionary *readinessRecord;
@property(nonatomic, copy) NSString *readinessDigest;
@property(nonatomic, copy) NSString *recoveryTransactionId;
@property(nonatomic, assign, readwrite) FacManPreviewState state;
@property(nonatomic, copy, readwrite) NSString *stateId;
@property(nonatomic, copy, readwrite) NSString *readiness;
@property(nonatomic, copy, readwrite) NSString *statusText;
@property(nonatomic, copy, readwrite) NSString *primaryLabel;
@property(nonatomic, copy, readwrite) NSString *primaryAccessibilityLabel;
@property(nonatomic, copy, readwrite) NSString *activitySummary;
@property(nonatomic, copy, readwrite) NSString *operationId;
@property(nonatomic, copy, readwrite) NSString *lastRun;
@property(nonatomic, copy, readwrite) NSString *recoveryId;
@property(nonatomic, copy, readwrite) NSString *refusalCode;
@property(nonatomic, copy, readwrite) NSString *refusalDetail;
@property(nonatomic, copy, readwrite) NSString *selectedInstanceId;
@property(nonatomic, copy, readwrite) NSString *instanceSummary;
@property(nonatomic, copy, readwrite) NSString *installationSummary;
@property(nonatomic, assign, readwrite) BOOL primaryEnabled;
@property(nonatomic, assign, readwrite) BOOL recoveryRequired;
@end

@implementation FacManLivePresentation

- (instancetype)initWithCommandClient:(FacManCommandClient *)client
{
    self = [super init];
    if (self) {
        _client = client;
        _selectedInstanceId = @"";
        _lastRun = @"No backend-completed run recorded";
        [self setUnavailable:@"Backend workspace has not been inspected" code:@"backend_not_inspected"];
    }
    return self;
}

- (void)refreshWithWorkspace:(NSString *)workspace cliPath:(NSString *)cliPath completion:(void (^)(void))completion
{
    [self.client executeCommandId:@"workspace.status" inputs:@{} workspace:workspace cliPath:cliPath completion:^(FacManCommandResult *workspaceResult) {
        if (workspaceResult.refused) { [self consumeFailure:workspaceResult completion:completion]; return; }
        [self.client executeCommandId:@"installs.scan" inputs:@{} workspace:workspace cliPath:cliPath completion:^(FacManCommandResult *installResult) {
            if (installResult.refused) { [self consumeFailure:installResult completion:completion]; return; }
            NSArray *installs = FacManArray(FacManPayload(installResult), @"installs");
            NSDictionary *install = [installs firstObject];
            NSString *installId = FacManText(install, @"install_id");
            if ([installId length] == 0) installId = FacManText(install, @"id");
            NSString *version = FacManText(install, @"version");
            self.installationSummary = [installs count] == 0 ? @"No supported installation discovered" :
                [NSString stringWithFormat:@"%lu installation(s); %@ %@", (unsigned long)[installs count], installId, version];
            [self.client executeCommandId:@"instance.list" inputs:@{} workspace:workspace cliPath:cliPath completion:^(FacManCommandResult *listResult) {
                if (listResult.refused) { [self consumeFailure:listResult completion:completion]; return; }
                NSArray *instances = FacManArray(FacManPayload(listResult), @"instances");
                NSDictionary *selected = [instances firstObject];
                NSString *instanceId = FacManText(selected, @"instance_id");
                if ([instanceId length] == 0) instanceId = FacManText(selected, @"id");
                self.selectedInstanceId = instanceId ?: @"";
                self.instanceSummary = [instances count] == 0 ? @"No backend instances; create one to continue" :
                    [NSString stringWithFormat:@"%lu instance(s); selected %@", (unsigned long)[instances count], self.selectedInstanceId];
                if ([self.selectedInstanceId length] == 0) {
                    [self setUnavailable:@"Select or create an instance" code:@"no_instance_selected"];
                    if (completion) completion();
                    return;
                }
                NSDictionary *inputs = @{ @"instance_id": self.selectedInstanceId };
                [self.client executeCommandId:@"instances.inspect" inputs:inputs workspace:workspace cliPath:cliPath completion:^(FacManCommandResult *inspectResult) {
                    if (inspectResult.refused) { [self consumeFailure:inspectResult completion:completion]; return; }
                    NSDictionary *inspection = FacManPayload(inspectResult);
                    NSString *name = FacManText(inspection, @"display_name");
                    if ([name length] > 0) self.instanceSummary = [NSString stringWithFormat:@"%@ — %@", name, self.selectedInstanceId];
                    [self.client executeCommandId:@"instances.readiness" inputs:inputs workspace:workspace cliPath:cliPath completion:^(FacManCommandResult *readyResult) {
                        if (readyResult.refused) { [self consumeFailure:readyResult completion:completion]; return; }
                        self.readinessRecord = FacManPayload(readyResult);
                        self.readinessDigest = FacManText(self.readinessRecord, @"readiness_digest");
                        [self.client executeCommandId:@"workspace.recovery.inspect" inputs:@{} workspace:workspace cliPath:cliPath completion:^(FacManCommandResult *recoveryResult) {
                            if (recoveryResult.refused) { [self consumeFailure:recoveryResult completion:completion]; return; }
                            [self consumeRecovery:FacManPayload(recoveryResult)];
                            if (self.recoveryRequired) {
                                self.lastRun = @"Superseded by incomplete backend recovery journal";
                            } else {
                                self.lastRun = @"Authoritative Last Run unavailable in this compatibility shell";
                            }
                            [self projectReadiness];
                            if (completion) completion();
                        }];
                    }];
                }];
            }];
        }];
    }];
}

- (void)playWithWorkspace:(NSString *)workspace cliPath:(NSString *)cliPath completion:(void (^)(void))completion
{
    NSString *observed = self.readinessDigest ?: @"";
    NSDictionary *inputs = @{ @"instance_id": self.selectedInstanceId ?: @"" };
    [self.client executeCommandId:@"instances.readiness" inputs:inputs workspace:workspace cliPath:cliPath completion:^(FacManCommandResult *readyResult) {
        if (readyResult.refused) { [self consumeFailure:readyResult completion:completion]; return; }
        self.readinessRecord = FacManPayload(readyResult);
        self.readinessDigest = FacManText(self.readinessRecord, @"readiness_digest");
        if (![observed isEqualToString:self.readinessDigest]) {
            [self setUnavailable:@"Workspace evidence changed; backend readiness was refreshed and no process started" code:@"stale_readiness"];
            if (completion) completion();
            return;
        }
        BOOL enabled = [[self.readinessRecord objectForKey:@"execution_available"] boolValue];
        [self.client executeExactRegisteredCommandId:@"run.execute" inputs:inputs workspace:workspace cliPath:cliPath backendEnabled:enabled completion:^(FacManCommandResult *runResult) {
            if (runResult.refused) { [self consumeFailure:runResult completion:completion]; return; }
            [self refreshWithWorkspace:workspace cliPath:cliPath completion:completion];
        }];
    }];
}

- (void)recoverWithWorkspace:(NSString *)workspace cliPath:(NSString *)cliPath completion:(void (^)(void))completion
{
    if ([self.recoveryTransactionId length] == 0) { if (completion) completion(); return; }
    [self.client executeCommandId:@"workspace.recovery.apply"
                           inputs:@{ @"transaction_id": self.recoveryTransactionId }
                        workspace:workspace cliPath:cliPath completion:^(FacManCommandResult *result) {
        if (result.refused) { [self consumeFailure:result completion:completion]; return; }
        [self refreshWithWorkspace:workspace cliPath:cliPath completion:completion];
    }];
}

- (void)projectReadiness
{
    if (self.recoveryRequired) return;
    BOOL enabled = [[self.readinessRecord objectForKey:@"execution_available"] boolValue];
    NSString *overall = FacManText(self.readinessRecord, @"overall_state");
    NSString *freshness = FacManText(self.readinessRecord, @"freshness");
    self.readiness = [NSString stringWithFormat:@"%@ — %@", overall, freshness];
    self.primaryEnabled = enabled;
    self.primaryLabel = [self.lastRun hasPrefix:@"Exited"] ? @"Relaunch" : @"Play";
    self.primaryAccessibilityLabel = enabled ? self.primaryLabel : @"Play unavailable; backend readiness refused execution";
    self.activitySummary = @"No active backend recovery operation.";
    self.operationId = @"";
    if (enabled) {
        self.state = [self.lastRun hasPrefix:@"Exited"] ? FacManPreviewStateExited : FacManPreviewStateReady;
        self.stateId = self.state == FacManPreviewStateExited ? @"exited" : @"positive";
        self.statusText = self.state == FacManPreviewStateExited ? @"Backend-completed Last Run retained; ready to relaunch" : @"Backend enabled exact Play route";
        self.refusalCode = @"";
        self.refusalDetail = @"";
    } else {
        NSDictionary *blocker = [FacManArray(self.readinessRecord, @"blockers") firstObject];
        NSString *code = FacManText(blocker, @"code");
        NSString *detail = FacManText(blocker, @"detail");
        [self setUnavailable:[detail length] > 0 ? detail : @"Backend did not enable exact Play route"
                         code:[code length] > 0 ? code : @"play_route_unavailable"];
    }
}

- (void)consumeRecovery:(NSDictionary *)payload
{
    NSMutableArray *transactions = [NSMutableArray array];
    for (NSDictionary *candidate in FacManArray(payload, @"transactions")) {
        NSString *state = FacManText(candidate, @"state");
        BOOL terminal = [state isEqualToString:@"complete"] || [state isEqualToString:@"refused"] ||
            [state isEqualToString:@"rolled_back"] || [state isEqualToString:@"cancelled"];
        if (!terminal) [transactions addObject:candidate];
    }
    NSDictionary *transaction = [transactions firstObject];
    self.recoveryRequired = [transactions count] > 0;
    self.recoveryTransactionId = FacManText(transaction, @"transaction_id");
    if ([self.recoveryTransactionId length] == 0) self.recoveryTransactionId = FacManText(transaction, @"id");
    if (!self.recoveryRequired) return;
    self.state = FacManPreviewStateInterrupted;
    self.stateId = @"interrupted";
    self.statusText = @"Backend recovery required after interruption";
    self.primaryLabel = @"Inspect recovery";
    self.primaryAccessibilityLabel = @"Inspect backend recovery transaction";
    self.primaryEnabled = YES;
    self.activitySummary = @"A backend journal transaction requires explicit recovery.";
    self.operationId = FacManText(transaction, @"operation_id");
    self.recoveryId = self.recoveryTransactionId;
    self.refusalCode = @"";
    self.refusalDetail = @"";
}

- (void)setUnavailable:(NSString *)detail code:(NSString *)code
{
    self.state = FacManPreviewStateStaleReadiness;
    self.stateId = @"refused";
    self.readiness = [NSString stringWithFormat:@"Unavailable — %@", code ?: @"play_route_unavailable"];
    self.statusText = [NSString stringWithFormat:@"Play unavailable — %@", code ?: @"play_route_unavailable"];
    self.primaryLabel = @"Play";
    self.primaryAccessibilityLabel = @"Play unavailable by backend refusal";
    self.primaryEnabled = NO;
    self.activitySummary = @"No process started by the frontend.";
    self.operationId = @"";
    self.recoveryId = @"";
    self.refusalCode = code ?: @"play_route_unavailable";
    self.refusalDetail = detail ?: @"Backend state unavailable";
}

- (void)consumeFailure:(FacManCommandResult *)result completion:(void (^)(void))completion
{
    [self setUnavailable:result.refusalReason code:result.refusalCode];
    if (completion) completion();
}

@end

static NSDictionary *FacManPayload(FacManCommandResult *result)
{
    NSData *data = [result.stdoutText dataUsingEncoding:NSUTF8StringEncoding];
    NSDictionary *envelope = data == nil ? nil : [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    id payload = [envelope objectForKey:@"payload"];
    return [payload isKindOfClass:[NSDictionary class]] ? payload : @{};
}

static NSString *FacManText(NSDictionary *record, NSString *key)
{
    id value = [record objectForKey:key];
    return [value isKindOfClass:[NSString class]] ? value : @"";
}

static NSArray *FacManArray(NSDictionary *record, NSString *key)
{
    id value = [record objectForKey:key];
    return [value isKindOfClass:[NSArray class]] ? value : @[];
}
