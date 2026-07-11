// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import "CliProcessClient.h"
#import "CommandClient.h"

static const NSTimeInterval FacManCliTimeoutSeconds = 30.0;

static NSString *FacManPipeText(NSData *data);
static FacManCommandResult *FacManDecodeResult(
    FacManCommandDefinition *command,
    NSInteger exitCode,
    NSString *stdoutText,
    NSString *stderrText);

@implementation FacManCliProcessClient

- (void)invokeCommand:(FacManCommandDefinition *)command
            arguments:(NSArray<NSString *> *)arguments
            workspace:(NSString *)workspace
              cliPath:(NSString *)cliPath
           completion:(FacManCliProcessCompletion)completion
{
    NSString *executable = [self resolveExecutable:cliPath];
    if ([executable length] == 0) {
        completion([FacManCommandResult refusalWithCommandId:command.commandId
                                                   backendId:command.backendId
                                                refusalCode:@"frontend_backend_unavailable"
                                              refusalReason:@"No facman CLI executable is configured, bundled with the AppKit app, or available through FACMAN_CLI."]);
        return;
    }

    NSMutableArray<NSString *> *fullArguments = [NSMutableArray array];
    NSString *trimmedWorkspace = [workspace stringByTrimmingCharactersInSet:
        [NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if ([trimmedWorkspace length] > 0) {
        [fullArguments addObject:@"--workspace"];
        [fullArguments addObject:trimmedWorkspace];
    }
    [fullArguments addObjectsFromArray:arguments ?: @[]];

    @try {
        NSTask *task = [[NSTask alloc] init];
        [task setLaunchPath:executable];
        [task setArguments:fullArguments];
        NSPipe *stdoutPipe = [NSPipe pipe];
        NSPipe *stderrPipe = [NSPipe pipe];
        [task setStandardOutput:stdoutPipe];
        [task setStandardError:stderrPipe];

        dispatch_group_t group = dispatch_group_create();
        __block NSData *stdoutData = nil;
        __block NSData *stderrData = nil;
        __block BOOL timedOut = NO;
        dispatch_group_async(group, dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
            stdoutData = [[stdoutPipe fileHandleForReading] readDataToEndOfFile];
        });
        dispatch_group_async(group, dispatch_get_global_queue(QOS_CLASS_UTILITY, 0), ^{
            stderrData = [[stderrPipe fileHandleForReading] readDataToEndOfFile];
        });
        dispatch_group_enter(group);
        [task setTerminationHandler:^(NSTask *finishedTask) {
            (void)finishedTask;
            dispatch_group_leave(group);
        }];
        [task launch];

        dispatch_after(
            dispatch_time(DISPATCH_TIME_NOW, (int64_t)(FacManCliTimeoutSeconds * NSEC_PER_SEC)),
            dispatch_get_global_queue(QOS_CLASS_UTILITY, 0),
            ^{
                if ([task isRunning]) {
                    timedOut = YES;
                    [task terminate];
                }
            });

        dispatch_group_notify(group, dispatch_get_main_queue(), ^{
            if (timedOut) {
                completion([FacManCommandResult refusalWithCommandId:command.commandId
                                                           backendId:command.backendId
                                                        refusalCode:@"frontend_backend_timeout"
                                                      refusalReason:@"The backend command exceeded the AppKit command timeout and was terminated."]);
                return;
            }
            completion(FacManDecodeResult(
                command,
                [task terminationStatus],
                FacManPipeText(stdoutData),
                FacManPipeText(stderrData)));
        });
    } @catch (NSException *exception) {
        completion([FacManCommandResult refusalWithCommandId:command.commandId
                                                   backendId:command.backendId
                                                refusalCode:@"frontend_backend_error"
                                              refusalReason:[exception reason] ?: @"AppKit command transport failed."]);
    }
}

- (NSString *)resolveExecutable:(NSString *)configuredPath
{
    NSFileManager *fileManager = [NSFileManager defaultManager];
    NSString *trimmedPath = [configuredPath stringByTrimmingCharactersInSet:
        [NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if ([trimmedPath length] > 0 && [fileManager isExecutableFileAtPath:trimmedPath]) return trimmedPath;
    NSString *envPath = [[[NSProcessInfo processInfo] environment] objectForKey:@"FACMAN_CLI"];
    envPath = [envPath stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if ([envPath length] > 0 && [fileManager isExecutableFileAtPath:envPath]) return envPath;
    NSString *bundledPath = [[NSBundle mainBundle] pathForResource:@"facman" ofType:nil];
    if ([bundledPath length] > 0 && [fileManager isExecutableFileAtPath:bundledPath]) return bundledPath;
    return @"facman";
}

@end

static NSString *FacManPipeText(NSData *data)
{
    NSString *text = [[NSString alloc] initWithData:data ?: [NSData data] encoding:NSUTF8StringEncoding];
    return text ?: @"";
}

static NSString *FacManDictionaryText(NSDictionary *dictionary, NSString *key)
{
    id value = [dictionary objectForKey:key];
    return [value isKindOfClass:[NSString class]] ? value : @"";
}

static FacManCommandResult *FacManDecodeResult(
    FacManCommandDefinition *command,
    NSInteger exitCode,
    NSString *stdoutText,
    NSString *stderrText)
{
    NSData *data = [stdoutText dataUsingEncoding:NSUTF8StringEncoding];
    NSDictionary *document = data == nil ? nil : [NSJSONSerialization JSONObjectWithData:data options:0 error:nil];
    NSDictionary *refusal = [[document objectForKey:@"refusal"] isKindOfClass:[NSDictionary class]]
        ? [document objectForKey:@"refusal"] : nil;
    NSDictionary *error = [[document objectForKey:@"error"] isKindOfClass:[NSDictionary class]]
        ? [document objectForKey:@"error"] : nil;
    NSDictionary *detail = refusal ?: error;
    BOOL refused = exitCode != 0 || [[document objectForKey:@"status"] isEqual:@"refused"] || detail != nil;
    return [[FacManCommandResult alloc] initWithCommandId:command.commandId
                                                backendId:command.backendId
                                                 exitCode:exitCode
                                               stdoutText:stdoutText
                                               stderrText:stderrText
                                                  refused:refused
                                              refusalCode:FacManDictionaryText(detail, @"code")
                                            refusalReason:FacManDictionaryText(detail, refusal != nil ? @"reason" : @"message")];
}
