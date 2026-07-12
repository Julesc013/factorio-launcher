// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import "CommandClient.h"
#import "CliProcessClient.h"
#import "FacManGeneratedCommandCatalog.h"

static NSString *FacManJsonEscape(NSString *value);

@implementation FacManCommandDefinition

- (instancetype)initWithCommandId:(NSString *)commandId
                        backendId:(NSString *)backendId
                           screen:(NSString *)screen
                            label:(NSString *)label
                          summary:(NSString *)summary
                   deferredReason:(NSString *)deferredReason
                            status:(FacManCommandStatus)status
                          labelKey:(NSString *)labelKey
                    descriptionKey:(NSString *)descriptionKey
                      availability:(NSString *)availability
                          riskTier:(NSString *)riskTier
                           effects:(NSString *)effects
                  inputDefinitions:(NSString *)inputDefinitions
                       positionals:(NSString *)positionals
                           options:(NSString *)options
                          renderer:(NSString *)renderer
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
        _labelKey = [labelKey copy];
        _descriptionKey = [descriptionKey copy];
        _availability = [availability copy];
        _riskTier = [riskTier copy];
        _effects = [effects copy];
        _inputDefinitions = [inputDefinitions copy];
        _positionals = [positionals copy];
        _options = [options copy];
        _renderer = [renderer copy];
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
                          outcome:(NSString *)outcome
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
        _outcome = [outcome copy] ?: (refused ? @"refused" : @"ok");
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
                                            refusalReason:refusalReason
                                                  outcome:@"refused"];
}

- (NSString *)displayText
{
    NSMutableString *text = [NSMutableString string];
    [text appendFormat:@"Command: %@\n", self.commandId];
    [text appendFormat:@"Backend: %@\n", self.backendId];
    [text appendFormat:@"Exit code: %ld\n", (long)self.exitCode];
    [text appendFormat:@"Outcome: %@\n", self.outcome];
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
    return FacManGeneratedCommandCatalog();
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

- (void)executeCommandId:(NSString *)commandId
                                   inputs:(NSDictionary<NSString *, NSString *> *)inputs
                                workspace:(NSString *)workspace
                                  cliPath:(NSString *)cliPath
                               completion:(void (^)(FacManCommandResult *result))completion
{
    FacManCommandDefinition *command = [[self class] definitionForCommandId:commandId];
    if (command == nil) {
        completion([FacManCommandResult refusalWithCommandId:commandId
                                               backendId:@"unknown"
                                            refusalCode:@"appkit_unknown_command"
                                          refusalReason:@"The AppKit shell has no command definition for this command id."]);
        return;
    }
    if (command.status != FacManCommandStatusImplemented) {
        completion([FacManCommandResult refusalWithCommandId:command.commandId
                                               backendId:command.backendId
                                            refusalCode:@"appkit_command_deferred"
                                          refusalReason:command.deferredReason]);
        return;
    }

    NSString *error = nil;
    NSDictionary<NSString *, id> *payload = FacManGeneratedPayload(command, inputs ?: @{}, &error);
    if (payload == nil) {
        completion([FacManCommandResult refusalWithCommandId:command.commandId
                                               backendId:command.backendId
                                            refusalCode:@"appkit_input_required"
                                          refusalReason:error ?: @"Missing required command input."]);
        return;
    }

    FacManCliProcessClient *transport = [[FacManCliProcessClient alloc] init];
    [transport invokeCommand:command
                     payload:payload
                   workspace:workspace
                     cliPath:cliPath
                  completion:completion];
}

@end

static NSString *FacManJsonEscape(NSString *value)
{
    if (value == nil) {
        return @"";
    }
    NSString *escaped = [value stringByReplacingOccurrencesOfString:@"\\" withString:@"\\\\"];
    return [escaped stringByReplacingOccurrencesOfString:@"\"" withString:@"\\\""];
}
