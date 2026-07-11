#import <Foundation/Foundation.h>

@class FacManCommandDefinition;
@class FacManCommandResult;

typedef void (^FacManCliProcessCompletion)(FacManCommandResult *result);

@interface FacManCliProcessClient : NSObject

- (void)invokeCommand:(FacManCommandDefinition *)command
            arguments:(NSArray<NSString *> *)arguments
            workspace:(NSString *)workspace
              cliPath:(NSString *)cliPath
           completion:(FacManCliProcessCompletion)completion;

@end
