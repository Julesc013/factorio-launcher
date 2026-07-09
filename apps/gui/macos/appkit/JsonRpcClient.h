#import <Foundation/Foundation.h>

@class FacManCommandDefinition;
@class FacManCommandResult;

@interface FacManJsonRpcClient : NSObject

- (FacManCommandResult *)invokeCommand:(FacManCommandDefinition *)command
                             arguments:(NSArray<NSString *> *)arguments
                             workspace:(NSString *)workspace
                               cliPath:(NSString *)cliPath;

@end
