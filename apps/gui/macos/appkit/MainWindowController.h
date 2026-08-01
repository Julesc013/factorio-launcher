// SPDX-FileCopyrightText: 2026 Jules C
// SPDX-License-Identifier: MIT

#import <Cocoa/Cocoa.h>

@interface MainWindowController : NSWindowController
- (void)showInstances:(id)sender;
- (void)showInstallations:(id)sender;
- (void)showActivity:(id)sender;
- (void)showSettingsAbout:(id)sender;
- (void)showAdvanced:(id)sender;
- (void)restoreSystemNative:(id)sender;
@end
