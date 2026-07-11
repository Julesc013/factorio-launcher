#import "CommandClient.h"
#import "JsonRpcClient.h"

static NSString *const FacManDeferredReason =
    @"Deferred in FACMAN-APPKIT-SHELL-01. The AppKit shell must render the command state without implementing backend behavior.";

static NSString *FacManJsonEscape(NSString *value);
static FacManCommandDefinition *FacManImplemented(NSString *commandId, NSString *backendId, NSString *screen, NSString *label, NSString *summary);
static FacManCommandDefinition *FacManDeferred(NSString *commandId, NSString *backendId, NSString *screen, NSString *label);
static NSArray<NSString *> *FacManArgumentsForCommand(NSString *commandId, NSDictionary<NSString *, NSString *> *inputs, NSString **error);
static NSString *FacManRequired(NSDictionary<NSString *, NSString *> *inputs, NSString *key, NSString **error);
static void FacManAddOptional(NSMutableArray<NSString *> *args, NSDictionary<NSString *, NSString *> *inputs, NSString *key, NSString *flag);

@implementation FacManCommandDefinition

- (instancetype)initWithCommandId:(NSString *)commandId
                        backendId:(NSString *)backendId
                           screen:(NSString *)screen
                            label:(NSString *)label
                          summary:(NSString *)summary
                   deferredReason:(NSString *)deferredReason
                            status:(FacManCommandStatus)status
{
    self = [super init];
    if (self) {
        _commandId = [commandId copy];
        _backendId = [backendId copy];
        _screen = [screen copy];
        _label = [label copy];
        _summary = [summary copy];
        _deferredReason = [deferredReason copy];
        _status = status;
    }
    return self;
}

@end

@implementation FacManCommandResult

- (instancetype)initWithCommandId:(NSString *)commandId
                        backendId:(NSString *)backendId
                         exitCode:(NSInteger)exitCode
                       stdoutText:(NSString *)stdoutText
                       stderrText:(NSString *)stderrText
                          refused:(BOOL)refused
                      refusalCode:(NSString *)refusalCode
                    refusalReason:(NSString *)refusalReason
{
    self = [super init];
    if (self) {
        _commandId = [commandId copy];
        _backendId = [backendId copy];
        _exitCode = exitCode;
        _stdoutText = [stdoutText copy] ?: @"";
        _stderrText = [stderrText copy] ?: @"";
        _refused = refused;
        _refusalCode = [refusalCode copy] ?: @"";
        _refusalReason = [refusalReason copy] ?: @"";
    }
    return self;
}

+ (instancetype)refusalWithCommandId:(NSString *)commandId
                            backendId:(NSString *)backendId
                         refusalCode:(NSString *)refusalCode
                       refusalReason:(NSString *)refusalReason
{
    NSString *json = [NSString stringWithFormat:
        @"{\n  \"schema\": \"common.refusal.v1\",\n  \"operation\": \"%@\",\n  \"backend_id\": \"%@\",\n  \"code\": \"%@\",\n  \"reason\": \"%@\",\n  \"recoverable\": true\n}",
        FacManJsonEscape(commandId),
        FacManJsonEscape(backendId),
        FacManJsonEscape(refusalCode),
        FacManJsonEscape(refusalReason)];
    return [[FacManCommandResult alloc] initWithCommandId:commandId
                                                backendId:backendId
                                                 exitCode:1
                                               stdoutText:json
                                               stderrText:@""
                                                  refused:YES
                                              refusalCode:refusalCode
                                            refusalReason:refusalReason];
}

- (NSString *)displayText
{
    NSMutableString *text = [NSMutableString string];
    [text appendFormat:@"Command: %@\n", self.commandId];
    [text appendFormat:@"Backend: %@\n", self.backendId];
    [text appendFormat:@"Exit code: %ld\n", (long)self.exitCode];
    if (self.refused) {
        [text appendFormat:@"Refusal: %@\n", self.refusalCode];
        [text appendFormat:@"Reason: %@\n", self.refusalReason];
    }
    if ([self.stdoutText length] > 0) {
        [text appendFormat:@"\nstdout:\n%@\n", self.stdoutText];
    }
    if ([self.stderrText length] > 0) {
        [text appendFormat:@"\nstderr:\n%@\n", self.stderrText];
    }
    return text;
}

@end

@implementation FacManCommandClient

+ (NSArray<FacManCommandDefinition *> *)catalog
{
    return @[
        FacManImplemented(@"help", @"app.help", @"Dashboard", @"Help", @"Render the shared CLI help text."),
        FacManImplemented(@"version", @"app.version", @"Dashboard", @"Version", @"Render the backend version."),
        FacManImplemented(@"doctor", @"doctor.run", @"Doctor", @"Doctor", @"Run workspace checks through the shared backend."),
        FacManImplemented(@"product.inspect", @"product.inspect", @"Dashboard", @"Product Inspect", @"Inspect the FacMan product binding."),
        FacManImplemented(@"command_graph.inspect", @"command_graph.inspect", @"Dashboard", @"Command Graph", @"Inspect the shared command graph."),
        FacManImplemented(@"installs.scan", @"installs.scan", @"Installs", @"Scan Installs", @"Ask the backend to scan for local install candidates."),
        FacManImplemented(@"installs.import", @"installs.import", @"Installs", @"Import Install", @"Register an existing local install reference through the backend."),
        FacManImplemented(@"installs.inspect", @"installs.inspect", @"Installs", @"Inspect Install", @"Inspect a registered install reference."),
        FacManImplemented(@"instances.list", @"instance.list", @"Instances", @"List Instances", @"List isolated instances from the backend workspace."),
        FacManImplemented(@"instances.create", @"instances.create", @"Instances", @"Create Instance", @"Create an isolated instance through the backend."),
        FacManImplemented(@"launch_plan.build", @"launch_plan.build", @"Launch Plan", @"Build Launch Plan", @"Build a dry-run launch plan through the backend."),
        FacManImplemented(@"launch_plan.preflight", @"launch_plan.preflight", @"Launch Plan", @"Preflight Launch", @"Validate the routed launch plan without starting a process."),
        FacManImplemented(@"run.preview", @"run.preview", @"Launch Plan", @"Run Preview", @"Preview run arguments without launching Factorio."),
        FacManImplemented(@"diagnostics.export", @"diagnostics.run", @"Diagnostics", @"Export Diagnostics", @"Export a diagnostics report from the shared backend."),
        FacManDeferred(@"run.execute", @"run.execute", @"Launch Plan", @"Execute Run"),
        FacManDeferred(@"modsets.lock", @"modsets.lock", @"Diagnostics", @"Lock Modset"),
        FacManDeferred(@"saves.backup", @"saves.backup", @"Diagnostics", @"Backup Save"),
        FacManDeferred(@"instance.export", @"instance.export", @"Diagnostics", @"Export Instance"),
        FacManDeferred(@"instance.import", @"instance.import", @"Diagnostics", @"Import Instance"),
        FacManDeferred(@"setup.preview", @"install_local.plan", @"Installs", @"Setup Preview")
    ];
}

+ (FacManCommandDefinition *)definitionForCommandId:(NSString *)commandId
{
    for (FacManCommandDefinition *command in [self catalog]) {
        if ([command.commandId isEqualToString:commandId]) {
            return command;
        }
    }
    return nil;
}

- (FacManCommandResult *)executeCommandId:(NSString *)commandId
                                   inputs:(NSDictionary<NSString *, NSString *> *)inputs
                                workspace:(NSString *)workspace
                                  cliPath:(NSString *)cliPath
{
    FacManCommandDefinition *command = [[self class] definitionForCommandId:commandId];
    if (command == nil) {
        return [FacManCommandResult refusalWithCommandId:commandId
                                               backendId:@"unknown"
                                            refusalCode:@"appkit_unknown_command"
                                          refusalReason:@"The AppKit shell has no command definition for this command id."];
    }
    if (command.status != FacManCommandStatusImplemented) {
        return [FacManCommandResult refusalWithCommandId:command.commandId
                                               backendId:command.backendId
                                            refusalCode:@"appkit_command_deferred"
                                          refusalReason:command.deferredReason];
    }

    NSString *error = nil;
    NSArray<NSString *> *arguments = FacManArgumentsForCommand(command.commandId, inputs ?: @{}, &error);
    if (arguments == nil) {
        return [FacManCommandResult refusalWithCommandId:command.commandId
                                               backendId:command.backendId
                                            refusalCode:@"appkit_input_required"
                                          refusalReason:error ?: @"Missing required command input."];
    }

    FacManJsonRpcClient *transport = [[FacManJsonRpcClient alloc] init];
    return [transport invokeCommand:command
                          arguments:arguments
                          workspace:workspace
                            cliPath:cliPath];
}

@end

static FacManCommandDefinition *FacManImplemented(NSString *commandId, NSString *backendId, NSString *screen, NSString *label, NSString *summary)
{
    return [[FacManCommandDefinition alloc] initWithCommandId:commandId
                                                    backendId:backendId
                                                       screen:screen
                                                        label:label
                                                      summary:summary
                                               deferredReason:@""
                                                        status:FacManCommandStatusImplemented];
}

static FacManCommandDefinition *FacManDeferred(NSString *commandId, NSString *backendId, NSString *screen, NSString *label)
{
    return [[FacManCommandDefinition alloc] initWithCommandId:commandId
                                                    backendId:backendId
                                                       screen:screen
                                                        label:label
                                                      summary:@"Deferred command."
                                               deferredReason:FacManDeferredReason
                                                        status:FacManCommandStatusNotSupportedWithReason];
}

static NSArray<NSString *> *FacManArgumentsForCommand(NSString *commandId, NSDictionary<NSString *, NSString *> *inputs, NSString **error)
{
    if ([commandId isEqualToString:@"help"]) {
        return @[ @"--help" ];
    }
    if ([commandId isEqualToString:@"version"]) {
        return @[ @"--version" ];
    }
    if ([commandId isEqualToString:@"doctor"]) {
        return @[ @"doctor", @"--json" ];
    }
    if ([commandId isEqualToString:@"product.inspect"]) {
        return @[ @"product", @"inspect", @"--json" ];
    }
    if ([commandId isEqualToString:@"command_graph.inspect"]) {
        return @[ @"command-graph", @"inspect", @"--json" ];
    }
    if ([commandId isEqualToString:@"installs.scan"]) {
        NSMutableArray<NSString *> *args = [NSMutableArray arrayWithObjects:@"installs", @"scan", @"--json", nil];
        FacManAddOptional(args, inputs, @"scanPath", @"--path");
        return args;
    }
    if ([commandId isEqualToString:@"installs.import"]) {
        NSString *path = FacManRequired(inputs, @"installPath", error);
        NSString *installId = FacManRequired(inputs, @"installId", error);
        if (path == nil || installId == nil) {
            return nil;
        }
        return @[ @"installs", @"import", path, @"--id", installId, @"--json" ];
    }
    if ([commandId isEqualToString:@"installs.inspect"]) {
        NSString *installId = FacManRequired(inputs, @"installId", error);
        return installId == nil ? nil : @[ @"installs", @"inspect", installId, @"--json" ];
    }
    if ([commandId isEqualToString:@"instances.list"]) {
        return @[ @"instances", @"list", @"--json" ];
    }
    if ([commandId isEqualToString:@"instances.create"]) {
        NSString *name = FacManRequired(inputs, @"instanceName", error);
        NSString *installId = FacManRequired(inputs, @"installId", error);
        if (name == nil || installId == nil) {
            return nil;
        }
        NSMutableArray<NSString *> *args = [NSMutableArray arrayWithObjects:@"instances", @"create", name, @"--install", installId, @"--json", nil];
        FacManAddOptional(args, inputs, @"templateId", @"--template");
        return args;
    }
    if ([commandId isEqualToString:@"launch_plan.build"]) {
        NSString *instanceId = FacManRequired(inputs, @"instanceId", error);
        return instanceId == nil ? nil : @[ @"launch-plan", instanceId, @"--json" ];
    }
    if ([commandId isEqualToString:@"launch_plan.preflight"]) {
        NSString *instanceId = FacManRequired(inputs, @"instanceId", error);
        return instanceId == nil ? nil : @[ @"launch-plan", instanceId, @"--preflight", @"--json" ];
    }
    if ([commandId isEqualToString:@"run.preview"]) {
        NSString *instanceId = FacManRequired(inputs, @"instanceId", error);
        return instanceId == nil ? nil : @[ @"run", instanceId, @"--json" ];
    }
    if ([commandId isEqualToString:@"diagnostics.export"]) {
        return @[ @"diagnostics", @"report", @"--json" ];
    }

    if (error != nil) {
        *error = [NSString stringWithFormat:@"No AppKit argument mapping for %@.", commandId];
    }
    return nil;
}

static NSString *FacManRequired(NSDictionary<NSString *, NSString *> *inputs, NSString *key, NSString **error)
{
    NSString *value = [inputs objectForKey:key];
    value = [value stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if ([value length] == 0) {
        if (error != nil) {
            *error = [NSString stringWithFormat:@"Missing required input: %@", key];
        }
        return nil;
    }
    return value;
}

static void FacManAddOptional(NSMutableArray<NSString *> *args, NSDictionary<NSString *, NSString *> *inputs, NSString *key, NSString *flag)
{
    NSString *value = [[inputs objectForKey:key] stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if ([value length] > 0) {
        [args addObject:flag];
        [args addObject:value];
    }
}

static NSString *FacManJsonEscape(NSString *value)
{
    if (value == nil) {
        return @"";
    }
    NSString *escaped = [value stringByReplacingOccurrencesOfString:@"\\" withString:@"\\\\"];
    return [escaped stringByReplacingOccurrencesOfString:@"\"" withString:@"\\\""];
}
