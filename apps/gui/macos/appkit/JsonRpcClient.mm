#import "JsonRpcClient.h"
#import "CommandClient.h"

static NSString *FacManReadPipe(NSPipe *pipe);

@implementation FacManJsonRpcClient

- (FacManCommandResult *)invokeCommand:(FacManCommandDefinition *)command
                             arguments:(NSArray<NSString *> *)arguments
                             workspace:(NSString *)workspace
                               cliPath:(NSString *)cliPath
{
    NSString *executable = [self resolveExecutable:cliPath];
    if ([executable length] == 0) {
        return [FacManCommandResult refusalWithCommandId:command.commandId
                                               backendId:command.backendId
                                            refusalCode:@"frontend_backend_unavailable"
                                          refusalReason:@"No facman CLI executable is configured, bundled with the AppKit app, or available through FACMAN_CLI."];
    }

    NSMutableArray<NSString *> *fullArguments = [NSMutableArray array];
    NSString *trimmedWorkspace = [workspace stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
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

        [task launch];
        [task waitUntilExit];

        NSString *stdoutText = FacManReadPipe(stdoutPipe);
        NSString *stderrText = FacManReadPipe(stderrPipe);
        return [[FacManCommandResult alloc] initWithCommandId:command.commandId
                                                    backendId:command.backendId
                                                     exitCode:[task terminationStatus]
                                                   stdoutText:stdoutText
                                                   stderrText:stderrText
                                                      refused:NO
                                                  refusalCode:@""
                                                refusalReason:@""];
    } @catch (NSException *exception) {
        return [FacManCommandResult refusalWithCommandId:command.commandId
                                               backendId:command.backendId
                                            refusalCode:@"frontend_backend_error"
                                          refusalReason:[exception reason] ?: @"AppKit command transport failed."];
    }
}

- (NSString *)resolveExecutable:(NSString *)configuredPath
{
    NSFileManager *fileManager = [NSFileManager defaultManager];
    NSString *trimmedPath = [configuredPath stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if ([trimmedPath length] > 0 && [fileManager isExecutableFileAtPath:trimmedPath]) {
        return trimmedPath;
    }

    NSString *envPath = [[[NSProcessInfo processInfo] environment] objectForKey:@"FACMAN_CLI"];
    envPath = [envPath stringByTrimmingCharactersInSet:[NSCharacterSet whitespaceAndNewlineCharacterSet]];
    if ([envPath length] > 0 && [fileManager isExecutableFileAtPath:envPath]) {
        return envPath;
    }

    NSString *bundledPath = [[NSBundle mainBundle] pathForResource:@"facman" ofType:nil];
    if ([bundledPath length] > 0 && [fileManager isExecutableFileAtPath:bundledPath]) {
        return bundledPath;
    }

    return @"facman";
}

@end

static NSString *FacManReadPipe(NSPipe *pipe)
{
    NSData *data = [[pipe fileHandleForReading] readDataToEndOfFile];
    NSString *text = [[NSString alloc] initWithData:data encoding:NSUTF8StringEncoding];
    return text ?: @"";
}
