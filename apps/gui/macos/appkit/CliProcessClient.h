// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import <Foundation/Foundation.h>

@class FacManCommandDefinition;
@class FacManCommandResult;

typedef void (^FacManCliProcessCompletion)(FacManCommandResult *result);

@interface FacManCliProcessClient : NSObject

- (void)invokeCommand:(FacManCommandDefinition *)command
              payload:(NSDictionary<NSString *, id> *)payload
            workspace:(NSString *)workspace
              cliPath:(NSString *)cliPath
           completion:(FacManCliProcessCompletion)completion;

@end
